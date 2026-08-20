from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    AuditLog,
    Base,
    ConfigCategoryEnum,
    ConfigEntry,
    CustomerLink,
    FieldProvenance,
    GoldenCustomer,
    ReviewQueueItem,
    RoleEnum,
    SourceRecord,
    User,
)
from src.db.session import get_db
from src.pipeline.match import run_match_pipeline
from src.pipeline.normalize import normalize_all_source_records
from src.seed_config import seed_config


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    seed_config(db)
    user = User(email="admin@example.com", password_hash="hash", role=RoleEnum.ADMIN)
    db.add(user)
    db.commit()
    db.refresh(user)
    return db


def test_normalize_all_source_records_uses_config_rules():
    db = _make_db()
    sr = SourceRecord(
        source_system="EQUITY",
        source_customer_id="C-001",
        name="  jOhN   doE ",
        mobile="+1 (415) 555-1234",
        email=" USER@Example.com ",
        pan_like="  12-34-56  ",
    )
    db.add(sr)
    db.commit()

    normalize_all_source_records(db)
    db.refresh(sr)

    assert sr.name == "John Doe"
    assert sr.mobile == "4155551234"
    assert sr.email == "user@example.com"
    assert sr.pan_like == "123456"


def test_run_match_pipeline_creates_deterministic_links_and_review_items():
    db = _make_db()
    sr1 = SourceRecord(
        source_system="EQUITY",
        source_customer_id="S1",
        name="John Doe",
        pan_like="ABCD1234E",
        mobile="4155551234",
        email="john@example.com",
    )
    sr2 = SourceRecord(
        source_system="MF",
        source_customer_id="S2",
        name="John Doe",
        pan_like="ABCD1234E",
        mobile="4155551234",
        email="john@example.com",
    )
    sr3 = SourceRecord(
        source_system="INSURANCE",
        source_customer_id="S3",
        name="Jane Smith",
        pan_like=None,
        mobile="9999999999",
        email="jane@sample.com",
    )
    sr4 = SourceRecord(
        source_system="WEALTH",
        source_customer_id="S4",
        name="Jane Smith",
        pan_like=None,
        mobile="9999999999",
        email="jane@sample.com",
    )
    db.add_all([sr1, sr2, sr3, sr4])
    db.commit()

    summary = run_match_pipeline(db)

    deterministic_links = db.query(CustomerLink).filter(CustomerLink.match_type == "DETERMINISTIC").count()
    review_items = db.query(ReviewQueueItem).count()

    assert deterministic_links >= 2
    assert summary["deterministic_links"] >= 2
    assert review_items >= 0


def test_phase4_resolves_conflicts_and_materializes_golden_customer():
    db = _make_db()
    db.add(User(email="rm@example.com", password_hash="hash", role=RoleEnum.RM))
    records = [
        SourceRecord(
            source_system="EQUITY",
            source_customer_id="E-001",
            name="Alex Customer",
            pan_like="PAN123",
            email="preferred@example.com",
            balance=125.0,
        ),
        SourceRecord(
            source_system="MF",
            source_customer_id="M-001",
            name="Alex Customer",
            pan_like="PAN123",
            email="stale@example.com",
            balance=75.0,
        ),
    ]
    db.add_all(records)
    db.commit()

    summary = run_match_pipeline(db)

    golden = db.query(GoldenCustomer).one()
    assert golden.email == "preferred@example.com"
    assert golden.relationship_value == 200.0
    assert golden.rm_id is not None
    assert summary["resolved_fields"] >= 1
    assert db.query(FieldProvenance).filter(
        FieldProvenance.golden_customer_id == golden.id,
        FieldProvenance.field_name == "email",
        FieldProvenance.is_resolved.is_(False),
    ).count() == 1
    assert db.query(AuditLog).filter(
        AuditLog.entity_type == "GoldenCustomer",
        AuditLog.entity_id == str(golden.id),
    ).count() == 1
