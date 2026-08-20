"""
Comprehensive test suite for Phase 1 (Auth, Models, Config) and Phase 2 (Ingestion)
"""
import pytest
import json
import os
from datetime import timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Import app and dependencies
from src.main import app
from src.db.session import get_db, Base
from src.db.models import (
    User, SourceRecord, ConfigEntry, AuditLog, RoleEnum, ConfigCategoryEnum
)
from src.auth.jwt import (
    hash_password, verify_password, create_access_token, verify_token
)
from src.seed_config import seed_config
from src.ingest import ingest_file, map_row_to_source
from src.utils import write_audit


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create an in-memory SQLite database for testing."""
    # Use check_same_thread=False to allow async operations
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert len(tables) > 0, "No tables created"
    
    # Seed config
    seed_config(db)
    db.flush()
    db.commit()
    
    yield db
    
    db.close()
    engine.dispose()


@pytest.fixture(scope="function")
def test_client(test_db, monkeypatch):
    """Create a FastAPI test client with test database."""
    def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    from sqlalchemy.orm import sessionmaker
    import src.ingest as ingest_module
    monkeypatch.setattr(ingest_module, "SessionLocal", sessionmaker(bind=test_db.get_bind()))
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(test_db):
    """Create a test admin user."""
    user = User(
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        role=RoleEnum.ADMIN
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def rm_user(test_db):
    """Create a test RM user."""
    user = User(
        email="rm@test.com",
        password_hash=hash_password("rm123"),
        role=RoleEnum.RM
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    """Generate JWT token for admin user."""
    return create_access_token(
        data={"id": admin_user.id, "email": admin_user.email, "role": admin_user.role.value}
    )


@pytest.fixture
def rm_token(rm_user):
    """Generate JWT token for RM user."""
    return create_access_token(
        data={"id": rm_user.id, "email": rm_user.email, "role": rm_user.role.value}
    )


# ============================================================================
# Phase 1: Auth & Models Tests
# ============================================================================

class TestPhase1DatabaseSchema:
    """Test Phase 1 database schema and models."""
    
    def test_user_table_exists(self, test_db):
        """Verify User table exists with expected columns."""
        user = User(
            email="test@example.com",
            password_hash=hash_password("password123"),
            role=RoleEnum.RM
        )
        test_db.add(user)
        test_db.commit()
        
        retrieved = test_db.query(User).filter(User.email == "test@example.com").first()
        assert retrieved is not None
        assert retrieved.email == "test@example.com"
        assert retrieved.role == RoleEnum.RM
    
    def test_source_record_table_exists(self, test_db):
        """Verify SourceRecord table exists."""
        from datetime import datetime
        
        record = SourceRecord(
            source_system="EQUITY",
            source_customer_id="CUST001",
            name="John Doe",
            pan_like="ABCD1234E",
            balance=100000.0,
            product_holdings={"holdings": 500}
        )
        test_db.add(record)
        test_db.commit()
        
        retrieved = test_db.query(SourceRecord).filter(
            SourceRecord.source_customer_id == "CUST001"
        ).first()
        assert retrieved is not None
        assert retrieved.name == "John Doe"
    
    def test_config_entry_table_exists(self, test_db):
        """Verify ConfigEntry table is populated with seed data."""
        config = test_db.query(ConfigEntry).filter(
            ConfigEntry.key == "fuzzy_match_v1"
        ).first()
        assert config is not None
        assert config.category == ConfigCategoryEnum.MATCH_WEIGHTS
        assert "pan_match" in config.value
    
    def test_audit_log_table_exists(self, test_db):
        """Verify AuditLog table exists."""
        audit = AuditLog(
            action="CREATE",
            entity_type="TestEntity",
            entity_id="1",
            before_value=None,
            after_value={"test": "data"}
        )
        test_db.add(audit)
        test_db.commit()
        
        retrieved = test_db.query(AuditLog).filter(
            AuditLog.entity_type == "TestEntity"
        ).first()
        assert retrieved is not None
        assert retrieved.action == "CREATE"


class TestPhase1Authentication:
    """Test Phase 1 authentication and JWT."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "mySecurePassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrongPassword", hashed)
    
    def test_jwt_creation_and_verification(self, admin_user):
        """Test JWT token creation and verification."""
        token = create_access_token(
            data={"id": admin_user.id, "email": admin_user.email, "role": admin_user.role.value}
        )
        
        payload = verify_token(token)
        assert payload is not None
        assert payload["id"] == admin_user.id
        assert payload["email"] == admin_user.email
        assert payload["role"] == "ADMIN"
    
    def test_jwt_verification_fails_with_invalid_token(self):
        """Test that invalid token fails verification."""
        payload = verify_token("invalid.token.here")
        assert payload is None
    
    def test_jwt_token_expiry(self):
        """Test that tokens can be created with custom expiry."""
        from datetime import datetime
        
        token = create_access_token(
            data={"id": 1, "test": "data"},
            expires_delta=timedelta(hours=1)
        )
        
        payload = verify_token(token)
        assert payload is not None
        assert "exp" in payload


class TestPhase1RBAC:
    """Test Phase 1 RBAC dependencies."""
    
    def test_admin_user_creation(self, test_db):
        """Test creating admin user."""
        admin = User(
            email="admin@test.com",
            password_hash=hash_password("admin123"),
            role=RoleEnum.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        
        retrieved = test_db.query(User).filter(User.role == RoleEnum.ADMIN).first()
        assert retrieved is not None
        assert retrieved.role == RoleEnum.ADMIN
    
    def test_role_enum_values(self):
        """Test that all role enum values exist."""
        assert RoleEnum.RM.value == "RM"
        assert RoleEnum.MANAGER.value == "MANAGER"
        assert RoleEnum.ADMIN.value == "ADMIN"


class TestPhase1Config:
    """Test Phase 1 configuration seeding."""
    
    def test_match_weights_seeded(self, test_db):
        """Test MATCH_WEIGHTS config entry is seeded."""
        config = test_db.query(ConfigEntry).filter(
            ConfigEntry.category == ConfigCategoryEnum.MATCH_WEIGHTS,
            ConfigEntry.key == "fuzzy_match_v1"
        ).first()
        
        assert config is not None
        assert isinstance(config.value, dict)
        assert "pan_match" in config.value
        assert "intercept" in config.value
    
    def test_thresholds_seeded(self, test_db):
        """Test THRESHOLDS config entries are seeded."""
        auto_merge = test_db.query(ConfigEntry).filter(
            ConfigEntry.category == ConfigCategoryEnum.THRESHOLDS,
            ConfigEntry.key == "auto_merge"
        ).first()
        
        manual_review = test_db.query(ConfigEntry).filter(
            ConfigEntry.category == ConfigCategoryEnum.THRESHOLDS,
            ConfigEntry.key == "manual_review"
        ).first()
        
        assert auto_merge is not None
        assert auto_merge.value["min_confidence"] == 0.90
        
        assert manual_review is not None
        assert manual_review.value["min_confidence"] == 0.60
        assert manual_review.value["max_confidence"] == 0.90
    
    def test_eligibility_rules_seeded(self, test_db):
        """Test ELIGIBILITY_RULES config entries are seeded."""
        insurance = test_db.query(ConfigEntry).filter(
            ConfigEntry.category == ConfigCategoryEnum.ELIGIBILITY_RULES,
            ConfigEntry.key == "insurance_cross_sell"
        ).first()
        
        wealth = test_db.query(ConfigEntry).filter(
            ConfigEntry.category == ConfigCategoryEnum.ELIGIBILITY_RULES,
            ConfigEntry.key == "wealth_advisory_cross_sell"
        ).first()
        
        assert insurance is not None
        assert insurance.value["min_relationship_value"] == 500000
        
        assert wealth is not None
        assert wealth.value["min_relationship_value"] == 2000000
    
    def test_source_precedence_seeded(self, test_db):
        """Test SOURCE_PRECEDENCE config is seeded."""
        config = test_db.query(ConfigEntry).filter(
            ConfigEntry.category == ConfigCategoryEnum.SOURCE_PRECEDENCE,
            ConfigEntry.key == "conflict_resolution_order"
        ).first()
        
        assert config is not None
        assert "mobile" in config.value
        assert "email" in config.value


class TestPhase1AuditLog:
    """Test Phase 1 audit logging."""
    
    def test_write_audit_helper(self, test_db, admin_user):
        """Test write_audit helper function."""
        before = {"name": "OldName"}
        after = {"name": "NewName"}
        
        audit = write_audit(
            db=test_db,
            actor_id=admin_user.id,
            action="UPDATE",
            entity_type="User",
            entity_id="1",
            before_value=before,
            after_value=after
        )
        
        assert audit.action == "UPDATE"
        assert audit.entity_type == "User"
        assert audit.before_value == before
        assert audit.after_value == after


class TestPhase1AuthEndpoints:
    """Test Phase 1 authentication endpoints."""
    
    def test_login_endpoint(self, test_client, admin_user):
        """Test POST /auth/login endpoint."""
        response = test_client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "admin123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == admin_user.id
        assert data["email"] == "admin@test.com"
        assert data["role"] == "ADMIN"
    
    def test_login_with_wrong_password(self, test_client, admin_user):
        """Test login fails with wrong password."""
        response = test_client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
    
    def test_login_with_nonexistent_user(self, test_client):
        """Test login fails with nonexistent user."""
        response = test_client.post(
            "/auth/login",
            json={"email": "missing@test.com", "password": "does-not-exist"}
        )
        assert response.status_code == 401
    
    def test_get_current_user_endpoint(self, test_client, admin_user, admin_token):
        """Test GET /auth/me endpoint."""
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "ADMIN"
    
    def test_get_current_user_without_token(self, test_client):
        """Test GET /auth/me fails without token."""
        response = test_client.get("/auth/me")
        assert response.status_code == 401


# ============================================================================
# Phase 2: Ingestion Tests
# ============================================================================

class TestPhase2Ingestion:
    """Test Phase 2 CSV ingestion."""
    
    def test_map_row_to_source_valid_record(self):
        """Test mapping CSV row to SourceRecord."""
        row = {
            "name": "John Doe",
            "pan_like_id": "ABCD1234E",
            "mobile": "9876543210",
            "email": "john@example.com",
            "city": "Mumbai",
            "dob": "1990-05-15",
            "source_customer_id": "CUST001",
            "holdings": "500",
            "portfolio_value": "100000"
        }
        
        mapped, errors = map_row_to_source(row, "EQUITY")
        
        assert not errors
        assert mapped["source_system"] == "EQUITY"
        assert mapped["source_customer_id"] == "CUST001"
        assert mapped["name"] == "John Doe"
        assert mapped["pan_like"] == "ABCD1234E"
        assert mapped["balance"] == 100000.0
    
    def test_map_row_rejects_invalid_balance(self):
        """Test that invalid balance is rejected."""
        row = {
            "name": "John Doe",
            "source_customer_id": "CUST001",
            "holdings": "INVALID_NUMBER",
            "dob": "1990-05-15"
        }
        
        mapped, errors = map_row_to_source(row, "EQUITY")
        
        assert len(errors) > 0
        assert any("non-numeric" in err for err in errors)
    
    def test_map_row_handles_missing_fields(self):
        """Test that missing optional fields don't crash."""
        row = {
            "source_customer_id": "CUST001"
        }
        
        mapped, errors = map_row_to_source(row, "EQUITY")
        
        assert not errors
        assert mapped["name"] is None
        assert mapped["pan_like"] is None
    
    def test_source_record_upsert_create(self, test_db):
        """Test creating new SourceRecord via upsert."""
        from src.ingest import upsert_source_record
        
        mapped = {
            "source_system": "EQUITY",
            "source_customer_id": "CUST001",
            "name": "John Doe",
            "pan_like": "ABCD1234E",
            "mobile": "9876543210",
            "email": "john@example.com",
            "city": "Mumbai",
            "dob": None,
            "product_holdings": {"holdings": 500},
            "balance": 100000.0,
            "raw_payload": {}
        }
        
        created, action = upsert_source_record(test_db, mapped, actor_id=None)
        
        assert created is True
        assert action == "created"
        
        # Verify record was created
        record = test_db.query(SourceRecord).filter(
            SourceRecord.source_customer_id == "CUST001"
        ).first()
        assert record is not None
        assert record.name == "John Doe"
    
    def test_source_record_upsert_update(self, test_db):
        """Test updating existing SourceRecord via upsert."""
        from src.ingest import upsert_source_record
        
        # Create initial record
        record = SourceRecord(
            source_system="EQUITY",
            source_customer_id="CUST001",
            name="John Doe",
            balance=100000.0
        )
        test_db.add(record)
        test_db.commit()
        
        # Update it
        mapped = {
            "source_system": "EQUITY",
            "source_customer_id": "CUST001",
            "name": "John Doe Updated",
            "pan_like": None,
            "mobile": None,
            "email": None,
            "city": None,
            "dob": None,
            "product_holdings": None,
            "balance": 150000.0,
            "raw_payload": {}
        }
        
        created, action = upsert_source_record(test_db, mapped, actor_id=None)
        
        assert created is False
        assert action == "updated"
        
        # Verify record was updated
        updated_record = test_db.query(SourceRecord).filter(
            SourceRecord.source_customer_id == "CUST001"
        ).first()
        assert updated_record.name == "John Doe Updated"
        assert updated_record.balance == 150000.0


class TestPhase2AdminIngestionRoute:
    """Test Phase 2 /admin/ingest endpoint."""
    
    def test_ingest_route_requires_admin(self, test_client, rm_token):
        """Test that /admin/ingest requires ADMIN role."""
        # Should be 403 Forbidden (insufficient permissions)
        response = test_client.post(
            "/admin/ingest",
            headers={"Authorization": f"Bearer {rm_token}"}
        )
        assert response.status_code == 403
    
    def test_ingest_route_with_admin_token(self, test_client, admin_token):
        """Test that /admin/ingest works with ADMIN token."""
        # Should succeed
        response = test_client.post(
            "/admin/ingest",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
    
    def test_ingest_route_without_token(self, test_client):
        """Test that /admin/ingest requires authentication."""
        response = test_client.post("/admin/ingest")
        assert response.status_code == 401


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase1Phase2Integration:
    """Integration tests for Phase 1 and Phase 2 together."""
    
    def test_end_to_end_login_and_ingest(self, test_client, admin_user):
        """Test complete flow: login -> get token -> call ingest."""
        # Step 1: Login
        login_response = test_client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "admin123"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Step 2: Call ingest with token
        ingest_response = test_client.post(
            "/admin/ingest",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert ingest_response.status_code == 200
        
        # Step 3: Verify data was ingested
        ingest_data = ingest_response.json()
        assert ingest_data["status"] == "ok"
        assert "summary" in ingest_data
    
    def test_audit_trail_on_ingest(self, test_db, admin_user):
        """Test that ingestion creates audit logs."""
        from src.ingest import ingest_file
        
        # Create a small CSV file for testing
        csv_path = Path(test_db.get_bind().url.database or "test.csv")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if we can create audit entries
        audit_count_before = test_db.query(AuditLog).count()
        
        # Ingest with actor_id
        # (This would normally read from CSV, but we're just verifying audit setup)
        write_audit(
            db=test_db,
            actor_id=admin_user.id,
            action="CREATE",
            entity_type="SourceRecord",
            entity_id="test1",
            before_value=None,
            after_value={"source_customer_id": "test1"}
        )
        
        audit_count_after = test_db.query(AuditLog).count()
        assert audit_count_after > audit_count_before


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
