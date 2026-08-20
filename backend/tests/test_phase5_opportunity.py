from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    AuditLog,
    Base,
    ConfigCategoryEnum,
    ConfigEntry,
    CustomerLink,
    GoldenCustomer,
    Opportunity,
    RoleEnum,
    SourceRecord,
    User,
)
from src.pipeline.opportunity import generate_opportunities
from src.seed_config import seed_config


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_local()
    seed_config(db)
    db.add(User(email="admin@example.com", password_hash="hash", role=RoleEnum.ADMIN))
    db.commit()
    return db


def _add_customer(db, relationship_value, systems, age_days=1):
    customer = GoldenCustomer(
        primary_name="Opportunity Customer",
        relationship_value=relationship_value,
    )
    db.add(customer)
    db.flush()
    created_at = datetime.utcnow() - timedelta(days=age_days)
    for index, system in enumerate(systems):
        record = SourceRecord(
            source_system=system,
            source_customer_id=f"{system}-{customer.id}",
            name="Opportunity Customer",
            balance=relationship_value / len(systems),
            created_at=created_at,
        )
        db.add(record)
        db.flush()
        db.add(
            CustomerLink(
                golden_customer_id=customer.id,
                source_record_id=record.id,
                match_type="DETERMINISTIC",
                confidence_score=1.0,
                match_reasons={"reason": "test"},
            )
        )
    db.commit()
    return customer


def test_creates_insurance_opportunity_for_equity_and_mf_customer():
    db = _make_db()
    customer = _add_customer(db, 5_000_000, ["EQUITY", "MF"])

    summary = generate_opportunities(db)

    opportunity = db.query(Opportunity).one()
    assert summary == {"opportunities_created": 1}
    assert opportunity.golden_customer_id == customer.id
    assert opportunity.product_type == "insurance_cross_sell"
    assert opportunity.eligibility_passed is True
    assert opportunity.reason_text
    assert opportunity.score_breakdown["weights"]["w1"] == 0.5
    assert db.query(AuditLog).filter(AuditLog.entity_type == "Opportunity").count() == 1


def test_missing_required_source_creates_no_opportunity():
    db = _make_db()
    _add_customer(db, 5_000_000, ["EQUITY"])

    generate_opportunities(db)

    assert db.query(Opportunity).count() == 0


def test_excluded_insurance_source_creates_no_insurance_opportunity():
    db = _make_db()
    _add_customer(db, 5_000_000, ["EQUITY", "MF", "INSURANCE"])

    generate_opportunities(db)

    assert db.query(Opportunity).filter(Opportunity.product_type == "insurance_cross_sell").count() == 0


def test_below_relationship_minimum_creates_no_opportunity():
    db = _make_db()
    _add_customer(db, 499_999, ["EQUITY", "MF"])

    generate_opportunities(db)

    assert db.query(Opportunity).count() == 0


def test_score_below_minimum_creates_no_opportunity():
    db = _make_db()
    customer = _add_customer(db, 5_000_000, ["EQUITY", "MF"], age_days=366)
    score_config = db.query(ConfigEntry).filter(
        ConfigEntry.category == ConfigCategoryEnum.SCORING_WEIGHTS,
        ConfigEntry.key == "opportunity_score_v1",
    ).one()
    score_config.value = {**score_config.value, "min_score": 90}
    db.commit()

    generate_opportunities(db)

    assert customer.relationship_value == 5_000_000
    assert db.query(Opportunity).count() == 0


def test_opportunity_generation_is_idempotent():
    db = _make_db()
    _add_customer(db, 5_000_000, ["EQUITY", "MF"])

    first = generate_opportunities(db)
    second = generate_opportunities(db)

    assert first == {"opportunities_created": 1}
    assert second == {"opportunities_created": 0}
    assert db.query(Opportunity).count() == 1
