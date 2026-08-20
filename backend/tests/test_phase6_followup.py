from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.auth.jwt import create_access_token, hash_password
from src.db.models import (
    AuditLog,
    Base,
    CustomerLink,
    FieldProvenance,
    GoldenCustomer,
    MatchTypeEnum,
    ReviewQueueItem,
    ReviewStatusEnum,
    RoleEnum,
    SourceRecord,
    User,
)
from src.db.session import get_db
from src.main import app
from src.pipeline.golden import materialize_golden_customers
from src.seed_config import seed_config


def _context():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    seed_config(db)
    manager = User(email="manager@followup", password_hash=hash_password("pw"), role=RoleEnum.MANAGER)
    rms = [User(email=f"rm{i}@followup", password_hash=hash_password("pw"), role=RoleEnum.RM) for i in range(1, 4)]
    admin = User(email="admin@followup", password_hash=hash_password("pw"), role=RoleEnum.ADMIN)
    db.add_all([manager, *rms, admin])
    db.flush()
    for rm in rms:
        rm.manager_id = manager.id
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    admin_headers = {"Authorization": f"Bearer {create_access_token({'id': admin.id, 'email': admin.email, 'role': 'ADMIN'})}"}
    return db, client, admin_headers, rms


def _unassigned_customer(db, index):
    customer = GoldenCustomer(primary_name=f"Round Robin {index}", relationship_value=100)
    db.add(customer)
    db.flush()
    record = SourceRecord(source_system="EQUITY", source_customer_id=f"RR-{index}", name=customer.primary_name, balance=100)
    db.add(record)
    db.flush()
    db.add(CustomerLink(
        golden_customer_id=customer.id,
        source_record_id=record.id,
        match_type=MatchTypeEnum.DETERMINISTIC,
        confidence_score=1.0,
        match_reasons={},
    ))
    return customer


def _match_review(db, index):
    first = SourceRecord(source_system="EQUITY", source_customer_id=f"MATCH-{index}-A", name="Match Candidate A")
    second = SourceRecord(source_system="MF", source_customer_id=f"MATCH-{index}-B", name="Match Candidate B")
    db.add_all([first, second])
    db.flush()
    item = ReviewQueueItem(
        candidate_source_record_id=first.id,
        candidate_source_record_id_2=second.id,
        reason="confidence in manual-review range, needs human decision",
        context={"confidence": 0.7, "features": {"name_similarity": 0.9}},
        status=ReviewStatusEnum.PENDING,
    )
    db.add(item)
    db.commit()
    return item, first, second


def test_round_robin_assigns_multiple_rms():
    db, _, _, rms = _context()
    customers = [_unassigned_customer(db, index) for index in range(6)]
    db.commit()
    materialize_golden_customers(db)
    assigned = {customer.rm_id for customer in customers}
    assert assigned.issubset({rm.id for rm in rms})
    assert len(assigned) >= 2
    app.dependency_overrides.clear()


def test_match_review_match_creates_one_golden_and_two_links():
    db, client, headers, _ = _context()
    item, first, second = _match_review(db, 1)
    response = client.post(
        f"/review-queue/{item.id}/resolve",
        headers=headers,
        json={"decision": "MATCH"},
    )
    assert response.status_code == 200
    db.refresh(item)
    assert item.status == ReviewStatusEnum.RESOLVED
    links = db.query(CustomerLink).filter(CustomerLink.source_record_id.in_([first.id, second.id])).all()
    assert len(links) == 2
    assert len({link.golden_customer_id for link in links}) == 1
    assert db.query(GoldenCustomer).count() == 1
    app.dependency_overrides.clear()


def test_match_review_no_match_rejects_without_outputs():
    db, client, headers, _ = _context()
    item, first, second = _match_review(db, 2)
    response = client.post(
        f"/review-queue/{item.id}/resolve",
        headers=headers,
        json={"decision": "NO_MATCH"},
    )
    assert response.status_code == 200
    db.refresh(item)
    assert item.status == ReviewStatusEnum.REJECTED
    assert db.query(GoldenCustomer).count() == 0
    assert db.query(CustomerLink).filter(CustomerLink.source_record_id.in_([first.id, second.id])).count() == 0
    app.dependency_overrides.clear()


def test_review_queue_context_and_field_conflict_resolution():
    db, client, headers, _ = _context()
    customer = GoldenCustomer(primary_name="Field Conflict", rm_id=None)
    db.add(customer)
    db.flush()
    record = SourceRecord(source_system="EQUITY", source_customer_id="FIELD-1", name="Field Conflict")
    db.add(record)
    db.flush()
    item = ReviewQueueItem(
        golden_customer_id=customer.id,
        candidate_source_record_id=record.id,
        reason="email conflict requires review",
        context={"field_name": "email", "candidate_values": [{"source_system": "EQUITY", "value": "old@example.com"}]},
        status=ReviewStatusEnum.PENDING,
    )
    db.add(item)
    db.commit()
    listed = client.get("/review-queue", headers=headers)
    body = next(row for row in listed.json() if row["id"] == item.id)
    assert body["context"]["field_name"] == "email"
    assert body["candidate_source_record_id_2"] is None
    response = client.post(
        f"/review-queue/{item.id}/resolve",
        headers=headers,
        json={"field_name": "email", "winning_value": "new@example.com", "winning_source_system": "EQUITY"},
    )
    assert response.status_code == 200
    provenance = db.query(FieldProvenance).filter(FieldProvenance.golden_customer_id == customer.id).one()
    assert provenance.value == "new@example.com"
    assert db.query(AuditLog).filter(AuditLog.entity_type == "ReviewQueueItem").count() == 1
    app.dependency_overrides.clear()
