from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth.jwt import get_current_user, require_role
from ..db.models import (
    CustomerLink,
    FieldProvenance,
    GoldenCustomer,
    MatchTypeEnum,
    ResolutionMethodEnum,
    ReviewQueueItem,
    ReviewStatusEnum,
    SourceRecord,
    User,
)
from ..db.session import get_db
from ..utils import write_audit
from ..pipeline.match import _create_customer_link, _existing_golden_for_records, _make_golden_customer
from .deps import can_unmask, mask_pii, scope_golden_customers

router = APIRouter()


class ResolveRequest(BaseModel):
    decision: str | None = None
    field_name: str | None = None
    winning_value: str | None = None
    winning_source_system: str | None = None


def _review_scope_query(db: Session, user: User):
    query = (
        db.query(ReviewQueueItem)
        .outerjoin(GoldenCustomer, ReviewQueueItem.golden_customer_id == GoldenCustomer.id)
        .outerjoin(SourceRecord, ReviewQueueItem.candidate_source_record_id == SourceRecord.id)
        .outerjoin(CustomerLink, CustomerLink.source_record_id == SourceRecord.id)
    )
    if user.role.value == "ADMIN":
        return query
    scoped_ids = scope_golden_customers(db.query(GoldenCustomer.id), user, db).subquery()
    return query.filter(
        or_(
            ReviewQueueItem.golden_customer_id.in_(scoped_ids),
            CustomerLink.golden_customer_id.in_(scoped_ids),
        )
    )


@router.get("/review-queue")
def list_review_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unmask: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    items = _review_scope_query(db, current_user).offset(offset).limit(limit).all()
    allowed_unmask = can_unmask(current_user, unmask)
    return [
        {
            "id": item.id,
            "golden_customer_id": item.golden_customer_id,
            "candidate_source_record_id": item.candidate_source_record_id,
            "candidate_source_record_id_2": item.candidate_source_record_id_2,
            "reason": item.reason,
            "context": item.context,
            "status": item.status.value,
            "candidate_source_record": {
                "pan_like": item.candidate_source_record.pan_like if allowed_unmask else mask_pii(item.candidate_source_record.pan_like),
                "mobile": item.candidate_source_record.mobile if allowed_unmask else mask_pii(item.candidate_source_record.mobile),
                "email": item.candidate_source_record.email if allowed_unmask else mask_pii(item.candidate_source_record.email),
            },
        }
        for item in items
    ]


@router.post("/review-queue/{item_id}/resolve")
def resolve_review_item(
    item_id: int,
    request: ResolveRequest,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    item = db.query(ReviewQueueItem).filter(ReviewQueueItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != ReviewStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Review item is already resolved")

    golden_id = item.golden_customer_id
    if golden_id is None:
        if request.decision not in {"MATCH", "NO_MATCH"}:
            raise HTTPException(status_code=400, detail="decision must be MATCH or NO_MATCH")
        if item.candidate_source_record_id_2 is None:
            raise HTTPException(status_code=400, detail="match review has no second candidate")

        before = {
            "status": item.status.value,
            "decision": None,
            "context": item.context,
        }
        if request.decision == "MATCH":
            records = [
                db.get(SourceRecord, item.candidate_source_record_id),
                db.get(SourceRecord, item.candidate_source_record_id_2),
            ]
            if any(record is None for record in records):
                raise HTTPException(status_code=404, detail="match candidates not found")
            golden = _existing_golden_for_records(db, records) or _make_golden_customer(db, records)
            for record in records:
                _create_customer_link(
                    db,
                    golden,
                    record,
                    MatchTypeEnum.PROBABILISTIC,
                    1.0,
                    {"reason": "manual_review_confirmed_match", "resolved_by": current_user.id},
                )
            golden_id = golden.id
        item.status = ReviewStatusEnum.RESOLVED if request.decision == "MATCH" else ReviewStatusEnum.REJECTED
        item.resolved_by = current_user.id
        item.resolved_at = datetime.utcnow()
        db.flush()
        write_audit(
            db,
            actor_id=current_user.id,
            action="RESOLVE",
            entity_type="ReviewQueueItem",
            entity_id=str(item.id),
            before_value=before,
            after_value={"status": item.status.value, "decision": request.decision},
        )
        return {"status": item.status.value.lower(), "id": item.id}

    if not request.field_name or request.winning_value is None or not request.winning_source_system:
        raise HTTPException(status_code=400, detail="field_name, winning_value, and winning_source_system are required")

    provenance = db.query(FieldProvenance).filter(
        FieldProvenance.golden_customer_id == golden_id,
        FieldProvenance.field_name == request.field_name,
        FieldProvenance.source_system == request.winning_source_system,
    ).first()
    if provenance is None:
        provenance = FieldProvenance(
            golden_customer_id=golden_id,
            field_name=request.field_name,
            source_system=request.winning_source_system,
        )
        db.add(provenance)
    provenance.value = request.winning_value
    provenance.confidence = 1.0
    provenance.is_resolved = True
    provenance.resolution_method = ResolutionMethodEnum.MANUAL
    item.status = ReviewStatusEnum.RESOLVED
    item.resolved_by = current_user.id
    item.resolved_at = datetime.utcnow()
    db.flush()
    write_audit(
        db,
        actor_id=current_user.id,
        action="RESOLVE",
        entity_type="ReviewQueueItem",
        entity_id=str(item.id),
        after_value={
            "field_name": request.field_name,
            "winning_value": request.winning_value,
            "winning_source_system": request.winning_source_system,
        },
    )
    return {"status": "resolved", "id": item.id}
