from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api import auth as auth_api
from src.db.models import (
    AuditLog,
    Base,
    ConfigEntry,
    CustomerLink,
    FieldProvenance,
    GoldenCustomer,
    MatchTypeEnum,
    Opportunity,
    ResolutionMethodEnum,
    ReviewQueueItem,
    ReviewStatusEnum,
    RoleEnum,
    SourceRecord,
    User,
)
from src.db.session import get_db
from src.main import app
from src.seed_config import seed_config
from src.auth.jwt import create_access_token, hash_password


def _make_context():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_local()
    seed_config(db)
    manager = User(email="manager@phase6", password_hash=hash_password("pw"), role=RoleEnum.MANAGER)
    rm1 = User(email="rm1@phase6", password_hash=hash_password("pw"), role=RoleEnum.RM)
    rm2 = User(email="rm2@phase6", password_hash=hash_password("pw"), role=RoleEnum.RM)
    admin = User(email="admin@phase6", password_hash=hash_password("pw"), role=RoleEnum.ADMIN)
    db.add_all([manager, rm1, rm2, admin])
    db.flush()
    rm1.manager_id = manager.id
    rm2.manager_id = manager.id
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    auth_api.limiter.reset()
    return db, session_local, manager, rm1, rm2, admin


def _client_and_tokens(db, manager, rm1, rm2, admin):
    client = TestClient(app)
    tokens = {
        "manager": create_access_token({"id": manager.id, "email": manager.email, "role": manager.role.value}),
        "rm1": create_access_token({"id": rm1.id, "email": rm1.email, "role": rm1.role.value}),
        "rm2": create_access_token({"id": rm2.id, "email": rm2.email, "role": rm2.role.value}),
        "admin": create_access_token({"id": admin.id, "email": admin.email, "role": admin.role.value}),
    }
    return client, {key: {"Authorization": f"Bearer {value}"} for key, value in tokens.items()}


def _customer(db, rm_id, number):
    customer = GoldenCustomer(
        primary_name=f"Customer {number}",
        pan_like=f"PAN{number}1234",
        mobile=f"900000{number:04d}",
        email=f"customer{number}@example.com",
        rm_id=rm_id,
        relationship_value=1_000_000,
    )
    db.add(customer)
    db.flush()
    record = SourceRecord(
        source_system="EQUITY",
        source_customer_id=f"C-{number}",
        name=customer.primary_name,
        pan_like=customer.pan_like,
        mobile=customer.mobile,
        email=customer.email,
    )
    db.add(record)
    db.flush()
    db.add(CustomerLink(
        golden_customer_id=customer.id,
        source_record_id=record.id,
        match_type=MatchTypeEnum.DETERMINISTIC,
        confidence_score=1.0,
        match_reasons={"reason": "test"},
    ))
    db.commit()
    return customer


def test_customer_scope_detail_forbidden_and_masking():
    db, _, manager, rm1, rm2, admin = _make_context()
    own = _customer(db, rm1.id, 1)
    other = _customer(db, rm2.id, 2)
    client, headers = _client_and_tokens(db, manager, rm1, rm2, admin)

    own_response = client.get("/customers", headers=headers["rm1"])
    assert own_response.status_code == 200
    assert [row["id"] for row in own_response.json()] == [own.id]
    assert own_response.json()[0]["pan_like"] != own.pan_like
    assert client.get(f"/customers/{other.id}", headers=headers["rm1"]).status_code == 403

    manager_response = client.get("/customers", headers=headers["manager"])
    assert {row["id"] for row in manager_response.json()} == {own.id, other.id}
    admin_response = client.get("/customers?unmask=true", headers=headers["admin"])
    assert admin_response.json()[0]["pan_like"] in {own.pan_like, other.pan_like}
    assert client.get("/customers?unmask=true", headers=headers["rm1"]).json()[0]["pan_like"] != own.pan_like
    app.dependency_overrides.clear()


def test_admin_sees_all_scoped_list_endpoints():
    db, _, manager, rm1, rm2, admin = _make_context()
    first = _customer(db, rm1.id, 3)
    second = _customer(db, rm2.id, 4)
    for customer in (first, second):
        db.add(Opportunity(
            golden_customer_id=customer.id,
            product_type="test_product",
            eligibility_passed=True,
            score=80,
            score_breakdown={},
            reason_text="test",
        ))
    db.commit()
    item = ReviewQueueItem(
        golden_customer_id=first.id,
        candidate_source_record_id=db.query(SourceRecord).filter(SourceRecord.source_customer_id == "C-3").one().id,
        reason="test review",
        status=ReviewStatusEnum.PENDING,
    )
    db.add(item)
    db.commit()
    client, headers = _client_and_tokens(db, manager, rm1, rm2, admin)
    assert len(client.get("/customers", headers=headers["admin"]).json()) == 2
    assert len(client.get("/opportunities", headers=headers["admin"]).json()) == 2
    assert len(client.get("/review-queue", headers=headers["admin"]).json()) == 1
    app.dependency_overrides.clear()


def test_review_resolve_admin_only_and_audited():
    db, _, manager, rm1, rm2, admin = _make_context()
    customer = _customer(db, rm1.id, 5)
    record = db.query(SourceRecord).filter(SourceRecord.source_customer_id == "C-5").one()
    item = ReviewQueueItem(
        golden_customer_id=customer.id,
        candidate_source_record_id=record.id,
        reason="email conflict",
        status=ReviewStatusEnum.PENDING,
    )
    db.add(item)
    db.commit()
    client, headers = _client_and_tokens(db, manager, rm1, rm2, admin)
    payload = {"field_name": "email", "winning_value": "winner@example.com", "winning_source_system": "EQUITY"}
    assert client.post(f"/review-queue/{item.id}/resolve", json=payload, headers=headers["rm1"]).status_code == 403
    response = client.post(f"/review-queue/{item.id}/resolve", json=payload, headers=headers["admin"])
    assert response.status_code == 200
    db.refresh(item)
    provenance = db.query(FieldProvenance).filter(FieldProvenance.golden_customer_id == customer.id).one()
    assert item.status == ReviewStatusEnum.RESOLVED
    assert provenance.value == "winner@example.com"
    assert provenance.resolution_method == ResolutionMethodEnum.MANUAL
    assert db.query(AuditLog).filter(AuditLog.entity_type == "ReviewQueueItem").count() == 1
    app.dependency_overrides.clear()


def test_config_update_version_and_audit_and_audit_log_rbac():
    db, _, manager, rm1, rm2, admin = _make_context()
    entry = db.query(ConfigEntry).first()
    old_value = entry.value
    old_version = entry.version
    client, headers = _client_and_tokens(db, manager, rm1, rm2, admin)
    assert client.get("/audit-log", headers=headers["rm1"]).status_code == 403
    response = client.put(f"/config/{entry.id}", json={"value": {"changed": True}}, headers=headers["admin"])
    assert response.status_code == 200
    db.refresh(entry)
    assert entry.version == old_version + 1
    audit = db.query(AuditLog).filter(AuditLog.entity_type == "ConfigEntry").one()
    assert audit.before_value == old_value
    assert audit.after_value == {"changed": True}
    assert client.get("/audit-log", headers=headers["admin"]).status_code == 200
    app.dependency_overrides.clear()


def test_login_rate_limit_returns_429_on_sixth_failed_attempt():
    db, _, manager, rm1, rm2, admin = _make_context()
    client = TestClient(app)
    statuses = [
        client.post("/auth/login", json={"email": "admin@phase6", "password": "wrong"}).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
    app.dependency_overrides.clear()


def test_audit_log_golden_customer_fields():
    db, _, manager, rm1, rm2, admin = _make_context()
    gc = GoldenCustomer(primary_name="Alice Smith", pan_like="ABCDE1234F")
    db.add(gc)
    db.commit()
    db.refresh(gc)

    audit_entry = AuditLog(
        actor_id=admin.id,
        action="admin_confirm_customer",
        entity_type="GoldenCustomer",
        entity_id=str(gc.id),
        before_value={"name": "Alice"},
        after_value={"name": "Alice Smith"},
    )
    db.add(audit_entry)
    db.commit()

    client, headers = _client_and_tokens(db, manager, rm1, rm2, admin)
    res = client.get("/audit-log?entity_type=GoldenCustomer", headers=headers["admin"])
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["entity_name"] == "Alice Smith"
    assert data[0]["entity_display_id"] == f"GC-{gc.id:05d}"
    app.dependency_overrides.clear()

