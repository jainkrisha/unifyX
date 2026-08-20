from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.jwt import get_current_user
from ..db.models import GoldenCustomer, Opportunity, User
from ..db.session import get_db
from .deps import can_unmask, mask_pii, scope_golden_customers

router = APIRouter()


@router.get("/opportunities")
def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unmask: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(Opportunity, GoldenCustomer).join(
        GoldenCustomer, Opportunity.golden_customer_id == GoldenCustomer.id
    )
    query = scope_golden_customers(query, current_user, db)
    allowed_unmask = can_unmask(current_user, unmask)
    return [
        {
            "id": opportunity.id,
            "golden_customer_id": opportunity.golden_customer_id,
            "product_type": opportunity.product_type,
            "eligibility_passed": opportunity.eligibility_passed,
            "score": opportunity.score,
            "score_breakdown": opportunity.score_breakdown,
            "reason_text": opportunity.reason_text,
            "status": opportunity.status,
            "customer": {
                "primary_name": customer.primary_name,
                "pan_like": customer.pan_like if allowed_unmask else mask_pii(customer.pan_like),
                "mobile": customer.mobile if allowed_unmask else mask_pii(customer.mobile),
                "email": customer.email if allowed_unmask else mask_pii(customer.email),
            },
        }
        for opportunity, customer in query.offset(offset).limit(limit).all()
    ]
