from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Set

from sqlalchemy.orm import Session

from src.db.models import (
    ConfigCategoryEnum,
    ConfigEntry,
    CustomerLink,
    GoldenCustomer,
    Opportunity,
    SourceRecord,
)
from src.pipeline.narrate import narrate_opportunity
from src.utils import write_audit


def _config_entries(db: Session, category: ConfigCategoryEnum) -> List[ConfigEntry]:
    return db.query(ConfigEntry).filter(ConfigEntry.category == category).all()


def _score_config(db: Session) -> Dict[str, float]:
    entry = next(iter(_config_entries(db, ConfigCategoryEnum.SCORING_WEIGHTS)), None)
    if entry is None or not isinstance(entry.value, dict):
        raise ValueError("SCORING_WEIGHTS configuration is missing")
    value = entry.value
    required = ("w1", "w2", "w3", "min_score")
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError(
            "SCORING_WEIGHTS configuration is missing: " + ", ".join(missing)
        )
    return {key: float(value[key]) for key in required}


def _linked_records(db: Session, golden_customer_id: int) -> List[SourceRecord]:
    return [
        record
        for record in (
            db.query(SourceRecord)
            .join(CustomerLink, CustomerLink.source_record_id == SourceRecord.id)
            .filter(CustomerLink.golden_customer_id == golden_customer_id)
            .all()
        )
    ]


def _recency_score(records: Iterable[SourceRecord], now: datetime) -> float:
    created_dates = [record.created_at for record in records if record.created_at]
    if not created_dates:
        return 0.0

    newest = max(created_dates)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - newest).total_seconds() / 86400)
    if age_days <= 30:
        return 100.0
    if age_days >= 365:
        return 0.0
    return round(100.0 * (365.0 - age_days) / (365.0 - 30.0), 2)


def generate_opportunities(db: Session) -> Dict[str, int]:
    score_config = _score_config(db)
    rules = _config_entries(db, ConfigCategoryEnum.ELIGIBILITY_RULES)
    created = 0
    now = datetime.now(timezone.utc)

    for golden_customer in db.query(GoldenCustomer).all():
        records = _linked_records(db, golden_customer.id)
        source_systems: Set[str] = {str(record.source_system) for record in records}

        for rule in rules:
            value = rule.value if isinstance(rule.value, dict) else {}
            required = set(value.get("requires", []))
            excluded = set(value.get("excludes", []))
            minimum_value = float(value.get("min_relationship_value", 0.0))
            eligible = (
                source_systems.issuperset(required)
                and source_systems.isdisjoint(excluded)
                and float(golden_customer.relationship_value or 0.0) >= minimum_value
            )
            if not eligible:
                continue

            potential_value_norm = min(
                100.0,
                (float(golden_customer.relationship_value or 0.0) / 10_000_000.0) * 100.0,
            )
            relationship_strength_norm = (len(source_systems) / 5.0) * 100.0
            recency_engagement_norm = _recency_score(records, now)
            score = round(
                score_config["w1"] * potential_value_norm
                + score_config["w2"] * relationship_strength_norm
                + score_config["w3"] * recency_engagement_norm,
                2,
            )
            if score < score_config["min_score"]:
                continue

            existing = (
                db.query(Opportunity)
                .filter(
                    Opportunity.golden_customer_id == golden_customer.id,
                    Opportunity.product_type == rule.key,
                )
                .first()
            )
            if existing:
                continue

            breakdown = {
                "potential_value_norm": potential_value_norm,
                "relationship_strength_norm": relationship_strength_norm,
                "recency_engagement_norm": recency_engagement_norm,
                "weights": {
                    "w1": score_config["w1"],
                    "w2": score_config["w2"],
                    "w3": score_config["w3"],
                },
            }
            opportunity = Opportunity(
                golden_customer_id=golden_customer.id,
                product_type=rule.key,
                eligibility_passed=True,
                score=score,
                score_breakdown=breakdown,
                reason_text=narrate_opportunity(
                    rule.key,
                    float(golden_customer.relationship_value or 0.0),
                    len(source_systems),
                    score,
                ),
                status="ACTIVE",
            )
            db.add(opportunity)
            db.flush()
            write_audit(
                db,
                actor_id=None,
                action="CREATE",
                entity_type="Opportunity",
                entity_id=str(opportunity.id),
                after_value={
                    "golden_customer_id": golden_customer.id,
                    "product_type": rule.key,
                    "score": score,
                },
            )
            created += 1

    return {"opportunities_created": created}
