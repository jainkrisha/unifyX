from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.jwt import require_role
from ..db.models import AuditLog, ConfigCategoryEnum, ConfigEntry, GoldenCustomer, User
from ..db.session import get_db
from ..utils import write_audit

router = APIRouter()


class ConfigUpdate(BaseModel):
    value: Any


def _config_payload(entry: ConfigEntry) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "category": entry.category.value,
        "key": entry.key,
        "value": entry.value,
        "version": entry.version,
        "updated_by": entry.updated_by,
    }


@router.get("/config")
def list_config(
    category: Optional[str] = None,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(ConfigEntry)
    if category:
        try:
            query = query.filter(ConfigEntry.category == ConfigCategoryEnum(category))
        except ValueError:
            return []
    return [_config_payload(entry) for entry in query.order_by(ConfigEntry.id).all()]


@router.put("/config/{config_id}")
def update_config(
    config_id: int,
    request: ConfigUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    entry = db.query(ConfigEntry).filter(ConfigEntry.id == config_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    before = entry.value
    write_audit(
        db,
        actor_id=current_user.id,
        action="UPDATE",
        entity_type="ConfigEntry",
        entity_id=str(entry.id),
        before_value=before,
        after_value=request.value,
    )
    entry.value = request.value
    entry.version = (entry.version or 1) + 1
    entry.updated_by = current_user.id
    db.commit()
    db.refresh(entry)
    return _config_payload(entry)


@router.get("/audit-log")
def list_audit_log(
    entity_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    rows = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()

    # Pre-fetch GoldenCustomer details for GoldenCustomer audit entries
    gc_ids = set()
    for row in rows:
        if row.entity_type == "GoldenCustomer" and row.entity_id:
            try:
                gc_ids.add(int(row.entity_id))
            except (ValueError, TypeError):
                pass
    gc_map = {}
    if gc_ids:
        customers = db.query(GoldenCustomer).filter(GoldenCustomer.id.in_(gc_ids)).all()
        gc_map = {c.id: c for c in customers}

    results = []
    for row in rows:
        entity_name = None
        entity_display_id = None
        if row.entity_type == "GoldenCustomer" and row.entity_id:
            try:
                gc_id = int(row.entity_id)
                cust = gc_map.get(gc_id)
                if cust:
                    entity_name = cust.primary_name
                    entity_display_id = f"GC-{gc_id:05d}"
            except (ValueError, TypeError):
                pass

        results.append({
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "entity_name": entity_name,
            "entity_display_id": entity_display_id,
            "before_value": row.before_value,
            "after_value": row.after_value,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        })
    return results

