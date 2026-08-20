import math
import logging
from typing import Any, Dict, Iterable, List, Optional, Set

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from sqlalchemy.orm import Session

from src.db.models import (
    ConfigCategoryEnum,
    ConfigEntry,
    CustomerLink,
    GoldenCustomer,
    MatchTypeEnum,
    ReviewQueueItem,
    ReviewStatusEnum,
    SourceRecord,
)
from src.pipeline.normalize import normalize_all_source_records


logger = logging.getLogger(__name__)


def _get_config_entry(db: Session, category: ConfigCategoryEnum, key: str) -> Optional[ConfigEntry]:
    return (
        db.query(ConfigEntry)
        .filter(ConfigEntry.category == category, ConfigEntry.key == key)
        .first()
    )


def _get_match_weights(db: Session) -> Dict[str, float]:
    entry = _get_config_entry(db, ConfigCategoryEnum.MATCH_WEIGHTS, "fuzzy_match_v1")
    if not entry or not isinstance(entry.value, dict):
        raise ValueError("MATCH_WEIGHTS/fuzzy_match_v1 configuration is missing")

    required_weights = (
        "pan_match",
        "name_similarity",
        "surname_similarity",
        "dob_match",
        "address_similarity",
        "mobile_match",
        "email_match",
        "intercept",
    )
    missing = [key for key in required_weights if key not in entry.value]
    if missing:
        raise ValueError(
            "MATCH_WEIGHTS/fuzzy_match_v1 is missing required weights: "
            + ", ".join(missing)
        )
    return {key: float(entry.value[key]) for key in required_weights}


def _get_thresholds(db: Session) -> Dict[str, float]:
    auto_entry = _get_config_entry(db, ConfigCategoryEnum.THRESHOLDS, "auto_merge")
    manual_entry = _get_config_entry(db, ConfigCategoryEnum.THRESHOLDS, "manual_review")

    auto_data = auto_entry.value if auto_entry and isinstance(auto_entry.value, dict) else {}
    manual_data = manual_entry.value if manual_entry and isinstance(manual_entry.value, dict) else {}

    return {
        "auto_merge": float(auto_data.get("min_confidence", 0.90)),
        "manual_min": float(manual_data.get("min_confidence", 0.60)),
        "manual_max": float(manual_data.get("max_confidence", 0.90)),
    }


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def _make_golden_customer(db: Session, records: Iterable[SourceRecord]) -> GoldenCustomer:
    record_list = list(records)
    primary = record_list[0]

    customer = GoldenCustomer(
        primary_name=primary.name or "Unknown Customer",
        pan_like=next((r.pan_like for r in record_list if r.pan_like), None),
        mobile=next((r.mobile for r in record_list if r.mobile), None),
        email=next((r.email for r in record_list if r.email), None),
        city=next((r.city for r in record_list if r.city), None),
        dob=next((r.dob for r in record_list if r.dob), None),
        relationship_value=0.0,
    )
    db.add(customer)
    db.flush()
    return customer


def _existing_golden_for_records(
    db: Session,
    records: Iterable[SourceRecord],
) -> Optional[GoldenCustomer]:
    record_ids = [record.id for record in records if record.id is not None]
    if not record_ids:
        return None
    link = (
        db.query(CustomerLink)
        .filter(CustomerLink.source_record_id.in_(record_ids))
        .order_by(CustomerLink.id.asc())
        .first()
    )
    return link.golden_customer if link else None


def _fuzzy_features(left: SourceRecord, right: SourceRecord) -> Dict[str, float]:
    pan_left = (left.pan_like or "").strip()
    pan_right = (right.pan_like or "").strip()
    pan_score = 0.0
    if pan_left and pan_right:
        pan_score = fuzz.ratio(pan_left, pan_right) / 100.0

    mobile_score = 1.0 if left.mobile and right.mobile and left.mobile == right.mobile else 0.0
    email_score = 1.0 if left.email and right.email and left.email == right.email else 0.0
    name_score = (
        JaroWinkler.normalized_similarity(left.name, right.name)
        if left.name and right.name
        else 0.0
    )
    left_surname = (left.name or "").split()[-1] if left.name else ""
    right_surname = (right.name or "").split()[-1] if right.name else ""
    surname_score = (
        JaroWinkler.normalized_similarity(left_surname, right_surname)
        if left_surname and right_surname
        else 0.0
    )
    dob_score = 1.0 if left.dob and right.dob and left.dob == right.dob else 0.0
    city_score = 1.0 if left.city and right.city and left.city == right.city else 0.0

    return {
        "pan_match": pan_score,
        "name_similarity": name_score,
        "surname_similarity": surname_score,
        "dob_match": dob_score,
        "address_similarity": city_score,
        "mobile_match": mobile_score,
        "email_match": email_score,
    }


def _compute_confidence(db: Session, features: Dict[str, float]) -> float:
    weights = _get_match_weights(db)
    value = weights["intercept"]
    for key in [
        "pan_match",
        "name_similarity",
        "surname_similarity",
        "dob_match",
        "address_similarity",
        "mobile_match",
        "email_match",
    ]:
        value += weights.get(key, 0.0) * float(features.get(key, 0.0))
    confidence = _sigmoid(value)
    if (
        features.get("pan_match") == 0.0
        and features.get("name_similarity") == 1.0
        and features.get("mobile_match") == 1.0
        and features.get("email_match") == 1.0
    ):
        logger.debug(
            "No-PAN crafted pair: features=%s weights=%s linear_score=%s confidence=%s thresholds=%s",
            features,
            weights,
            value,
            confidence,
            _get_thresholds(db),
        )
    return confidence


def _create_customer_link(
    db: Session,
    golden_customer: GoldenCustomer,
    source_record: SourceRecord,
    match_type: MatchTypeEnum,
    confidence: float,
    match_reasons: Dict[str, Any],
) -> CustomerLink:
    existing = (
        db.query(CustomerLink)
        .filter(
            CustomerLink.golden_customer_id == golden_customer.id,
            CustomerLink.source_record_id == source_record.id,
        )
        .first()
    )
    if existing:
        existing.match_type = match_type
        existing.confidence_score = float(confidence)
        existing.match_reasons = match_reasons
        return existing

    link = CustomerLink(
        golden_customer_id=golden_customer.id,
        source_record_id=source_record.id,
        match_type=match_type,
        confidence_score=float(confidence),
        match_reasons=match_reasons,
    )
    db.add(link)
    db.flush()
    return link


def run_match_pipeline(db: Session) -> Dict[str, Any]:
    normalize_all_source_records(db)

    records = db.query(SourceRecord).order_by(SourceRecord.id.asc()).all()
    thresholds = _get_thresholds(db)
    processed_ids: Set[int] = set()
    summary = {"deterministic_links": 0, "probabilistic_links": 0, "review_items": 0}

    pan_groups: Dict[str, List[SourceRecord]] = {}
    for record in records:
        if record.pan_like:
            pan_groups.setdefault(record.pan_like, []).append(record)

    for pan_value, group in pan_groups.items():
        if len(group) < 2:
            continue

        golden = _existing_golden_for_records(db, group) or _make_golden_customer(db, group)
        for record in group:
            if record.id in processed_ids:
                continue
            processed_ids.add(record.id)
            _create_customer_link(
                db,
                golden,
                record,
                MatchTypeEnum.DETERMINISTIC,
                1.0,
                {"reason": "exact_pan_match", "pan": pan_value},
            )
            summary["deterministic_links"] += 1

    remaining = [r for r in records if r.id not in processed_ids]
    for index, left in enumerate(remaining):
        for right in remaining[index + 1 :]:
            if left.id in processed_ids or right.id in processed_ids:
                continue

            features = _fuzzy_features(left, right)
            confidence = _compute_confidence(db, features)

            if confidence >= thresholds["auto_merge"]:
                golden = _existing_golden_for_records(db, [left, right]) or _make_golden_customer(db, [left, right])
                _create_customer_link(
                    db,
                    golden,
                    left,
                    MatchTypeEnum.PROBABILISTIC,
                    confidence,
                    {"reason": "fuzzy", "features": features, "confidence": round(confidence, 4)},
                )
                _create_customer_link(
                    db,
                    golden,
                    right,
                    MatchTypeEnum.PROBABILISTIC,
                    confidence,
                    {"reason": "fuzzy", "features": features, "confidence": round(confidence, 4)},
                )
                processed_ids.add(left.id)
                processed_ids.add(right.id)
                summary["probabilistic_links"] += 2
            elif thresholds["manual_min"] <= confidence < thresholds["manual_max"]:
                record = left if left.id < right.id else right
                existing_review = (
                    db.query(ReviewQueueItem)
                    .filter(
                        ReviewQueueItem.golden_customer_id.is_(None),
                        ReviewQueueItem.candidate_source_record_id == record.id,
                        ReviewQueueItem.status == ReviewStatusEnum.PENDING,
                    )
                    .first()
                )
                if existing_review is None:
                    db.add(
                        ReviewQueueItem(
                            golden_customer_id=None,
                            candidate_source_record_id=record.id,
                            reason="confidence in manual-review range, needs human decision",
                            status=ReviewStatusEnum.PENDING,
                        )
                    )
                processed_ids.add(left.id)
                processed_ids.add(right.id)
                summary["review_items"] += 1

    from src.pipeline.golden import materialize_golden_customers
    from src.pipeline.resolve import resolve_linked_customers

    resolution_summary = resolve_linked_customers(db)
    golden_summary = materialize_golden_customers(db)
    db.commit()
    summary.update(resolution_summary)
    summary.update(golden_summary)
    return summary
