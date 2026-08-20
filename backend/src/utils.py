"""Utility functions for the application."""
from typing import Optional, Any
from sqlalchemy.orm import Session
from .db.models import AuditLog


def write_audit(
    db: Session,
    actor_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: str,
    before_value: Optional[Any] = None,
    after_value: Optional[Any] = None
) -> AuditLog:
    """Write an audit log entry to track data changes.
    
    Args:
        db: Database session
        actor_id: ID of the user performing the action
        action: Action type (e.g., "CREATE", "UPDATE", "DELETE")
        entity_type: Type of entity being modified (e.g., "SourceRecord", "GoldenCustomer")
        entity_id: ID of the entity
        before_value: State before the change (optional)
        after_value: State after the change (optional)
    
    Returns:
        The created AuditLog entry
    """
    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before_value,
        after_value=after_value
    )
    db.add(audit_entry)
    db.commit()
    return audit_entry
