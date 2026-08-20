from fastapi import APIRouter, Depends, HTTPException, status
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import Dict
from ..db.session import get_db
from ..db.models import User
from ..auth.jwt import require_role

load_dotenv()

router = APIRouter()


@router.post("/admin/ingest")
def admin_ingest(
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
) -> Dict:
    """Ingest financial CSVs into SourceRecord.
    
    Requires: ADMIN role
    """
    from ..ingest import ingest_all

    summary = ingest_all(actor_id=current_user.id)
    return {"status": "ok", "summary": summary}


@router.post("/admin/run-pipeline")
def admin_run_pipeline(
    current_user: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
) -> Dict:
    """Run the Phase 3 matching and Phase 4 golden-customer pipeline.

    Requires: ADMIN role
    """
    from ..pipeline.match import run_match_pipeline

    summary = run_match_pipeline(db)
    return {"status": "ok", "summary": summary}
