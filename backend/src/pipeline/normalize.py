import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.db.models import ConfigCategoryEnum, ConfigEntry, SourceRecord


def _lookup_rules(db: Session) -> Dict[str, Dict[str, Any]]:
    rules: Dict[str, Dict[str, Any]] = {}
    entries = (
        db.query(ConfigEntry)
        .filter(ConfigEntry.category == ConfigCategoryEnum.NORMALIZATION_RULES)
        .all()
    )
    for entry in entries:
        if isinstance(entry.value, dict):
            rules[entry.key] = entry.value
    return rules


def _normalize_mobile(raw_value: Any, rules: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    digits = re.sub(r"\D", "", value)
    if not digits:
        return None

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) > 10:
        digits = digits[-10:]

    return digits or None


def _normalize_email(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None

    value = str(raw_value).strip().lower()
    if not value:
        return None
    return value


def _normalize_name(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    return cleaned.title()


def _normalize_pan(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None

    value = str(raw_value).strip().upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", value)
    if not cleaned:
        return None
    return cleaned


def normalize_record(record: SourceRecord, rules: Optional[Dict[str, Dict[str, Any]]] = None) -> SourceRecord:
    record.name = _normalize_name(record.name)
    record.mobile = _normalize_mobile(record.mobile, rules.get("mobile") if rules else None)
    record.email = _normalize_email(record.email)
    record.pan_like = _normalize_pan(record.pan_like)
    return record


def normalize_all_source_records(db: Session) -> Dict[str, int]:
    rules = _lookup_rules(db)
    updated = 0

    for record in db.query(SourceRecord).all():
        normalize_record(record, rules)
        updated += 1

    db.commit()
    return {"updated": updated}
