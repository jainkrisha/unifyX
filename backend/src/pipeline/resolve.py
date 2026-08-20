from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from src.db.models import (
    ConfigCategoryEnum,
    ConfigEntry,
    CustomerLink,
    AuditLog,
    FieldProvenance,
    ResolutionMethodEnum,
    ReviewQueueItem,
    ReviewStatusEnum,
    SourceRecord,
)
from src.utils import write_audit


RESOLVED_FIELDS = ("name", "mobile", "email", "city", "dob")


def _precedence_rules(db: Session) -> Dict[str, List[str]]:
    entry = (
        db.query(ConfigEntry)
        .filter(
            ConfigEntry.category == ConfigCategoryEnum.SOURCE_PRECEDENCE,
            ConfigEntry.key == "conflict_resolution_order",
        )
        .first()
    )
    value = entry.value if entry and isinstance(entry.value, dict) else {}
    return {
        field: [str(source) for source in sources]
        for field, sources in value.items()
        if isinstance(sources, list)
    }


def _field_value(record: SourceRecord, field: str) -> Optional[Any]:
    value = getattr(record, field)
    if value is None or value == "":
        return None
    return value


def _serialized(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _linked_groups(db: Session) -> Dict[int, List[SourceRecord]]:
    groups: Dict[int, List[SourceRecord]] = defaultdict(list)
    links = db.query(CustomerLink).order_by(CustomerLink.id.asc()).all()
    for link in links:
        if link.golden_customer_id and link.source_record:
            groups[link.golden_customer_id].append(link.source_record)
    return groups


def _add_review_item(
    db: Session,
    golden_customer_id: int,
    records: Iterable[SourceRecord],
    field: str,
    values: List[Any],
) -> None:
    record = next(iter(records))
    reason = (
        f"{field} conflict requires review: "
        f"{[_serialized(value) for value in values]}"
    )
    existing = (
        db.query(ReviewQueueItem)
        .filter(
            ReviewQueueItem.golden_customer_id == golden_customer_id,
            ReviewQueueItem.candidate_source_record_id == record.id,
            ReviewQueueItem.status == ReviewStatusEnum.PENDING,
        )
        .first()
    )
    if existing:
        existing.reason = reason
        return
    db.add(
        ReviewQueueItem(
            golden_customer_id=golden_customer_id,
            candidate_source_record_id=record.id,
            reason=reason,
            status=ReviewStatusEnum.PENDING,
        )
    )


def _upsert_provenance(
    db: Session,
    golden_customer_id: int,
    field_name: str,
    value: Any,
    source_system: str,
    confidence: float,
    is_resolved: bool,
    resolution_method: Optional[ResolutionMethodEnum],
) -> FieldProvenance:
    existing = (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.golden_customer_id == golden_customer_id,
            FieldProvenance.field_name == field_name,
            FieldProvenance.source_system == source_system,
        )
        .first()
    )
    if existing:
        existing.value = str(_serialized(value))
        existing.confidence = confidence
        existing.is_resolved = is_resolved
        existing.resolution_method = resolution_method
        return existing

    provenance = FieldProvenance(
        golden_customer_id=golden_customer_id,
        field_name=field_name,
        value=str(_serialized(value)),
        source_system=source_system,
        confidence=confidence,
        is_resolved=is_resolved,
        resolution_method=resolution_method,
    )
    db.add(provenance)
    return provenance


def _write_unique_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    before_value: Any,
    after_value: Any,
) -> None:
    existing = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == action,
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        .all()
    )
    if any(entry.before_value == before_value and entry.after_value == after_value for entry in existing):
        return
    write_audit(
        db,
        actor_id=None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before_value,
        after_value=after_value,
    )


def resolve_linked_customers(db: Session) -> Dict[str, int]:
    """Persist field-level provenance for every linked customer group."""
    precedence = _precedence_rules(db)
    summary = {"resolved_fields": 0, "conflicts": 0, "review_items": 0}

    for golden_customer_id, records in _linked_groups(db).items():
        for field in RESOLVED_FIELDS:
            values_by_record = [
                (record, _field_value(record, field))
                for record in records
            ]
            non_null = [(record, value) for record, value in values_by_record if value is not None]
            if not non_null:
                continue

            distinct_values = {_serialized(value) for _, value in non_null}
            if len(distinct_values) == 1:
                winning_record, winning_value = non_null[0]
                _upsert_provenance(
                    db,
                    golden_customer_id,
                    field,
                    winning_value,
                    str(winning_record.source_system),
                    1.0,
                    True,
                    ResolutionMethodEnum.SOURCE_PRECEDENCE,
                )
                summary["resolved_fields"] += 1
                continue

            summary["conflicts"] += 1
            ordered_sources = precedence.get(field, [])
            ordered_records = sorted(
                non_null,
                key=lambda pair: (
                    ordered_sources.index(str(pair[0].source_system))
                    if str(pair[0].source_system) in ordered_sources
                    else len(ordered_sources),
                    pair[0].id,
                ),
            )

            if not ordered_sources or all(
                str(record.source_system) not in ordered_sources
                for record, _ in non_null
            ):
                _add_review_item(
                    db,
                    golden_customer_id,
                    records,
                    field,
                    list(distinct_values),
                )
                summary["review_items"] += 1
                for record, value in non_null:
                    _upsert_provenance(
                        db,
                        golden_customer_id,
                        field,
                        value,
                        str(record.source_system),
                        0.0,
                        False,
                        None,
                    )
                continue

            winning_record, winning_value = ordered_records[0]
            for record, value in non_null:
                is_winner = record.id == winning_record.id
                _upsert_provenance(
                    db,
                    golden_customer_id,
                    field,
                    value,
                    str(record.source_system),
                    1.0 if is_winner else 0.0,
                    is_winner,
                    ResolutionMethodEnum.SOURCE_PRECEDENCE,
                )
            _write_unique_audit(
                db,
                "RESOLVE",
                "FieldProvenance",
                f"{golden_customer_id}:{field}",
                {
                    "field": field,
                    "values": [
                        {
                            "source_system": str(record.source_system),
                            "value": _serialized(value),
                        }
                        for record, value in non_null
                    ],
                },
                {
                    "source_system": str(winning_record.source_system),
                    "value": _serialized(winning_value),
                    "resolution_method": ResolutionMethodEnum.SOURCE_PRECEDENCE.value,
                },
            )
            summary["resolved_fields"] += 1

    db.flush()
    return summary