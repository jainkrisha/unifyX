from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth.jwt import get_current_user
from ..db.models import CustomerLink, FieldProvenance, GoldenCustomer, User
from ..db.session import get_db
from .deps import can_unmask, mask_pii, scope_golden_customers

router = APIRouter()


def _customer_payload(customer: GoldenCustomer, unmask: bool) -> Dict[str, Any]:
    pii = lambda value: value if unmask else mask_pii(value)
    return {
        "id": customer.id,
        "primary_name": customer.primary_name,
        "pan_like": pii(customer.pan_like),
        "mobile": pii(customer.mobile),
        "email": pii(customer.email),
        "city": customer.city,
        "dob": customer.dob.isoformat() if customer.dob else None,
        "relationship_value": customer.relationship_value,
        "rm_id": customer.rm_id,
    }


def _source_payload(record: Any, unmask: bool) -> Dict[str, Any]:
    return {
        "id": record.id,
        "source_system": record.source_system,
        "source_customer_id": record.source_customer_id,
        "name": record.name,
        "pan_like": record.pan_like if unmask else mask_pii(record.pan_like),
        "mobile": record.mobile if unmask else mask_pii(record.mobile),
        "email": record.email if unmask else mask_pii(record.email),
        "city": record.city,
        "dob": record.dob.isoformat() if record.dob else None,
        "product_holdings": record.product_holdings,
        "balance": record.balance,
        "raw_payload": record.raw_payload,
    }


@router.get("/customers")
def list_customers(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unmask: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = scope_golden_customers(db.query(GoldenCustomer), current_user, db)
    
    # Sort by the amount of field provenances (conflicts) so models with differences appear first
    query = query.outerjoin(FieldProvenance).group_by(GoldenCustomer.id).order_by(
        func.count(FieldProvenance.id).desc(),
        GoldenCustomer.id.desc()
    )

    return [_customer_payload(c, can_unmask(current_user, unmask)) for c in query.offset(offset).limit(limit).all()]


@router.get("/customers/{customer_id}")
def customer_detail(
    customer_id: int,
    unmask: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    customer = db.query(GoldenCustomer).filter(GoldenCustomer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if scope_golden_customers(
        db.query(GoldenCustomer).filter(GoldenCustomer.id == customer_id), current_user, db
    ).first() is None:
        raise HTTPException(status_code=403, detail="Customer outside your scope")

    allowed_unmask = can_unmask(current_user, unmask)
    links = db.query(CustomerLink).filter(CustomerLink.golden_customer_id == customer_id).all()
    return {
        "customer": _customer_payload(customer, allowed_unmask),
        "source_records": [_source_payload(link.source_record, allowed_unmask) for link in links],
        "field_provenance": [
            {
                "id": row.id,
                "field_name": row.field_name,
                "value": row.value,
                "source_system": row.source_system,
                "confidence": row.confidence,
                "is_resolved": row.is_resolved,
                "resolution_method": row.resolution_method.value if row.resolution_method else None,
            }
            for row in db.query(FieldProvenance).filter(FieldProvenance.golden_customer_id == customer_id).all()
        ],
        "match_reasons": [link.match_reasons for link in links],
    }
