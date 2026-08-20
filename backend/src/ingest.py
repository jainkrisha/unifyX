import os
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple
from sqlalchemy.exc import IntegrityError
from .db.session import SessionLocal
from .db.models import SourceRecord, AuditLog

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _parse_date(s: str):
    if not s or str(s).strip() == "":
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


def _to_float(val):
    try:
        return float(val)
    except Exception:
        return None


def map_row_to_source(record: dict, source_system: str) -> Tuple[dict, list]:
    # Map generic columns and product-specific columns into product_holdings
    errors = []
    name = record.get("name")
    pan = record.get("pan_like_id") or record.get("pan_like") or record.get("pan")
    mobile = record.get("mobile")
    email = record.get("email")
    city = record.get("city")
    dob = _parse_date(record.get("dob"))
    source_customer_id = record.get("source_customer_id")

    # Collect product_holdings depending on file columns
    product = {}
    # Known fields: holdings,portfolio_value,loan_amount,outstanding,emi,aum
    for k in ["holdings", "portfolio_value", "loan_amount", "outstanding", "emi", "aum"]:
        if k in record and record.get(k) not in (None, ""):
            v = _to_float(record.get(k))
            if v is None:
                errors.append(f"non-numeric {k}: {record.get(k)}")
            else:
                product[k] = v

    balance = None
    # prefer portfolio_value, outstanding, aum, loan_amount
    for key in ("portfolio_value", "outstanding", "aum", "loan_amount"):
        if key in product:
            balance = product[key]
            break

    payload = {**record}

    mapped = {
        "source_system": source_system,
        "source_customer_id": source_customer_id,
        "name": name,
        "pan_like": pan,
        "mobile": mobile,
        "email": email,
        "city": city,
        "dob": dob,
        "product_holdings": product,
        "balance": balance,
        "raw_payload": payload,
    }

    return mapped, errors


def upsert_source_record(db, mapped, actor_id=None) -> Tuple[bool, str]:
    # returns (created, action)
    existing = db.query(SourceRecord).filter_by(
        source_system=mapped["source_system"],
        source_customer_id=mapped["source_customer_id"],
    ).one_or_none()

    if existing:
        before = {
            "name": existing.name,
            "pan_like": existing.pan_like,
            "mobile": existing.mobile,
            "email": existing.email,
            "city": existing.city,
            "dob": existing.dob.isoformat() if existing.dob else None,
            "product_holdings": existing.product_holdings,
            "balance": existing.balance,
        }

        existing.name = mapped.get("name")
        existing.pan_like = mapped.get("pan_like")
        existing.mobile = mapped.get("mobile")
        existing.email = mapped.get("email")
        existing.city = mapped.get("city")
        existing.dob = mapped.get("dob")
        existing.product_holdings = mapped.get("product_holdings")
        existing.balance = mapped.get("balance")
        existing.raw_payload = mapped.get("raw_payload")

        after = {
            "name": existing.name,
            "pan_like": existing.pan_like,
            "mobile": existing.mobile,
            "email": existing.email,
            "city": existing.city,
            "dob": existing.dob.isoformat() if existing.dob else None,
            "product_holdings": existing.product_holdings,
            "balance": existing.balance,
        }

        db.add(AuditLog(actor_id=actor_id, action="UPDATE", entity_type="SourceRecord", entity_id=mapped["source_customer_id"], before_value=before, after_value=after))
        return False, "updated"
    else:
        sr = SourceRecord(
            source_system=mapped.get("source_system"),
            source_customer_id=mapped.get("source_customer_id"),
            name=mapped.get("name"),
            pan_like=mapped.get("pan_like"),
            mobile=mapped.get("mobile"),
            email=mapped.get("email"),
            city=mapped.get("city"),
            dob=mapped.get("dob"),
            product_holdings=mapped.get("product_holdings"),
            balance=mapped.get("balance"),
            raw_payload=mapped.get("raw_payload"),
        )
        db.add(sr)
        db.flush()
        db.add(AuditLog(actor_id=actor_id, action="CREATE", entity_type="SourceRecord", entity_id=sr.id, before_value=None, after_value={"source_customer_id": sr.source_customer_id}))
        return True, "created"


def ingest_file(path: str, source_system: str, actor_id=None) -> dict:
    df = pd.read_csv(path, dtype=str).fillna("")
    created = 0
    updated = 0
    rejected = 0
    reject_reasons = {}

    db = SessionLocal()
    try:
        for _, row in df.iterrows():
            record = row.to_dict()
            mapped, errors = map_row_to_source(record, source_system)
            if errors or not mapped.get("source_customer_id"):
                rejected += 1
                reason = ";".join(errors) if errors else "missing source_customer_id"
                reject_reasons.setdefault(reason, 0)
                reject_reasons[reason] += 1
                continue

            try:
                created_flag, action = upsert_source_record(db, mapped, actor_id=actor_id)
                if created_flag:
                    created += 1
                else:
                    updated += 1
                db.commit()
            except IntegrityError:
                db.rollback()
                rejected += 1
                reject_reasons.setdefault("db_integrity_error", 0)
                reject_reasons["db_integrity_error"] += 1
    finally:
        db.close()

    return {"created": created, "updated": updated, "rejected": rejected, "reject_reasons": reject_reasons}


def ingest_all(dir_path: str = None, files: dict = None, actor_id=None):
    # files: mapping of filename -> source_system
    if files is None:
        # default to backend/data/raw/financial
        base = Path(__file__).resolve().parents[1] / "data" / "raw" / "financial"
        files = {
            str(base / "equity.csv"): "EQUITY",
            str(base / "mutual_funds.csv"): "MF",
            str(base / "insurance.csv"): "INSURANCE",
            str(base / "loans.csv"): "LOANS",
            str(base / "wealth.csv"): "WEALTH",
        }

    summary = {}
    for p, system in files.items():
        if not Path(p).exists():
            summary[p] = {"error": "file not found"}
            continue
        summary[p] = ingest_file(p, system, actor_id=actor_id)

    return summary


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1] / "data" / "raw" / "financial"
    print("Ingesting from:", base)
    result = ingest_all()
    print(json.dumps(result, indent=2, default=str))
