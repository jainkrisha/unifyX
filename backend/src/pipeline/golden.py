from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.db.models import AuditLog, CustomerLink, FieldProvenance, GoldenCustomer, RoleEnum, User
from src.utils import write_audit


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _rm_cycle(db: Session):
    rms = db.query(User).filter(User.role == RoleEnum.RM).order_by(User.id.asc()).all()
    if not rms:
        return
    index = 0
    while True:
        yield rms[index % len(rms)].id
        index += 1


def _groups(db: Session) -> Dict[int, List[CustomerLink]]:
    grouped: Dict[int, List[CustomerLink]] = defaultdict(list)
    for link in db.query(CustomerLink).order_by(CustomerLink.id.asc()).all():
        grouped[link.golden_customer_id].append(link)
    return grouped


def _write_unique_audit(
    db: Session,
    entity_id: str,
    before_value: Dict[str, Any],
    after_value: Dict[str, Any],
) -> bool:
    existing = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "UPDATE",
            AuditLog.entity_type == "GoldenCustomer",
            AuditLog.entity_id == entity_id,
        )
        .all()
    )
    if any(entry.after_value == after_value for entry in existing):
        return False
    write_audit(
        db,
        actor_id=None,
        action="UPDATE",
        entity_type="GoldenCustomer",
        entity_id=entity_id,
        before_value=before_value,
        after_value=after_value,
    )
    return True


def materialize_golden_customers(db: Session) -> Dict[str, int]:
    """Apply resolved provenance and balances to the provisional golden rows."""
    summary = {"golden_customers": 0, "audit_entries": 0}
    rm_ids = _rm_cycle(db)

    for golden_id, links in _groups(db).items():
        golden = db.get(GoldenCustomer, golden_id)
        if golden is None:
            continue

        before = {
            "primary_name": golden.primary_name,
            "pan_like": golden.pan_like,
            "mobile": golden.mobile,
            "email": golden.email,
            "city": golden.city,
            "dob": golden.dob.isoformat() if golden.dob else None,
            "relationship_value": golden.relationship_value,
            "rm_id": golden.rm_id,
        }
        provenance = (
            db.query(FieldProvenance)
            .filter(
                FieldProvenance.golden_customer_id == golden_id,
                FieldProvenance.is_resolved.is_(True),
            )
            .order_by(FieldProvenance.id.asc())
            .all()
        )
        resolved: Dict[str, str] = {}
        for field in provenance:
            resolved.setdefault(field.field_name, field.value)

        if "name" in resolved:
            golden.primary_name = resolved["name"]
        for field in ("mobile", "email", "city"):
            if field in resolved:
                setattr(golden, field, resolved[field])
        if "dob" in resolved:
            # Keep the source datetime representation when possible.
            source_dob = next(
                (
                    link.source_record.dob
                    for link in links
                    if link.source_record and link.source_record.dob.isoformat() == resolved["dob"]
                ),
                None,
            )
            if source_dob is not None:
                golden.dob = source_dob

        golden.pan_like = next(
            (link.source_record.pan_like for link in links if link.source_record and link.source_record.pan_like),
            None,
        )
        golden.relationship_value = sum(
            _as_float(link.source_record.balance)
            for link in links
            if link.source_record is not None
        )
        if golden.rm_id is None:
            golden.rm_id = next(rm_ids, None)

        after = {
            "primary_name": golden.primary_name,
            "pan_like": golden.pan_like,
            "mobile": golden.mobile,
            "email": golden.email,
            "city": golden.city,
            "dob": golden.dob.isoformat() if golden.dob else None,
            "relationship_value": golden.relationship_value,
            "rm_id": golden.rm_id,
        }
        audit_created = _write_unique_audit(db, str(golden.id), before, after)
        summary["golden_customers"] += 1
        summary["audit_entries"] += int(audit_created)

    return summary