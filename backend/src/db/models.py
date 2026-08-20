from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, UniqueConstraint, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship

# Use JSON for SQLite compatibility; PostgreSQL will upgrade to JSONB automatically
JSON_TYPE = JSON
from sqlalchemy.sql import func
from .session import Base
import enum
import datetime


class RoleEnum(str, enum.Enum):
    RM = "RM"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class SourceSystemEnum(str, enum.Enum):
    EQUITY = "EQUITY"
    MF = "MF"
    INSURANCE = "INSURANCE"
    LOANS = "LOANS"
    WEALTH = "WEALTH"


class MatchTypeEnum(str, enum.Enum):
    DETERMINISTIC = "DETERMINISTIC"
    PROBABILISTIC = "PROBABILISTIC"


class ResolutionMethodEnum(str, enum.Enum):
    SOURCE_PRECEDENCE = "SOURCE_PRECEDENCE"
    MANUAL = "MANUAL"


class ReviewStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class ConfigCategoryEnum(str, enum.Enum):
    MATCH_WEIGHTS = "MATCH_WEIGHTS"
    THRESHOLDS = "THRESHOLDS"
    SOURCE_PRECEDENCE = "SOURCE_PRECEDENCE"
    ELIGIBILITY_RULES = "ELIGIBILITY_RULES"
    SCORING_WEIGHTS = "SCORING_WEIGHTS"
    REVIEW_RULES = "REVIEW_RULES"
    NORMALIZATION_RULES = "NORMALIZATION_RULES"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.RM)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Self-referential relationship for manager
    manager = relationship("User", remote_side=[id], foreign_keys=[manager_id], back_populates="managed_rms")
    managed_rms = relationship("User", foreign_keys=[manager_id], back_populates="manager")


class SourceRecord(Base):
    __tablename__ = "source_records"
    id = Column(Integer, primary_key=True)
    source_system = Column(String(64), nullable=False)
    source_customer_id = Column(String(128), nullable=False)
    name = Column(String(256))
    pan_like = Column(String(64), index=True)
    mobile = Column(String(64), index=True)
    email = Column(String(256), index=True)
    city = Column(String(128))
    dob = Column(DateTime)
    product_holdings = Column(JSON_TYPE)
    balance = Column(Float)
    raw_payload = Column(JSON_TYPE)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_system", "source_customer_id", name="uix_source_system_customer"),
    )


class GoldenCustomer(Base):
    __tablename__ = "golden_customers"
    id = Column(Integer, primary_key=True)
    primary_name = Column(String(256), nullable=False)
    pan_like = Column(String(64), index=True)
    mobile = Column(String(64), index=True)
    email = Column(String(256), index=True)
    city = Column(String(128))
    dob = Column(DateTime)
    relationship_value = Column(Float, default=0.0)
    rm_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    rm = relationship("User", foreign_keys=[rm_id])


class CustomerLink(Base):
    __tablename__ = "customer_links"
    id = Column(Integer, primary_key=True)
    golden_customer_id = Column(Integer, ForeignKey("golden_customers.id"), nullable=False)
    source_record_id = Column(Integer, ForeignKey("source_records.id"), nullable=False)
    match_type = Column(Enum(MatchTypeEnum), nullable=False)
    confidence_score = Column(Float, nullable=False)
    match_reasons = Column(JSON_TYPE)
    created_at = Column(DateTime, server_default=func.now())

    golden_customer = relationship("GoldenCustomer", foreign_keys=[golden_customer_id])
    source_record = relationship("SourceRecord", foreign_keys=[source_record_id])


class FieldProvenance(Base):
    __tablename__ = "field_provenances"
    id = Column(Integer, primary_key=True)
    golden_customer_id = Column(Integer, ForeignKey("golden_customers.id"), nullable=False)
    field_name = Column(String(128), nullable=False)
    value = Column(String(512))
    source_system = Column(String(64))
    confidence = Column(Float)
    is_resolved = Column(Boolean, default=False)
    resolution_method = Column(Enum(ResolutionMethodEnum), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    golden_customer = relationship("GoldenCustomer", foreign_keys=[golden_customer_id])


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    id = Column(Integer, primary_key=True)
    golden_customer_id = Column(Integer, ForeignKey("golden_customers.id"), nullable=True)
    candidate_source_record_id = Column(Integer, ForeignKey("source_records.id"), nullable=False)
    reason = Column(String(512))
    status = Column(Enum(ReviewStatusEnum), default=ReviewStatusEnum.PENDING, nullable=False)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    golden_customer = relationship("GoldenCustomer", foreign_keys=[golden_customer_id])
    candidate_source_record = relationship("SourceRecord", foreign_keys=[candidate_source_record_id])
    resolved_by_user = relationship("User", foreign_keys=[resolved_by])


class Opportunity(Base):
    __tablename__ = "opportunities"
    id = Column(Integer, primary_key=True)
    golden_customer_id = Column(Integer, ForeignKey("golden_customers.id"), nullable=False)
    product_type = Column(String(128), nullable=False)
    eligibility_passed = Column(Boolean, default=False)
    score = Column(Float, nullable=False)
    score_breakdown = Column(JSON_TYPE)
    reason_text = Column(String(1024))
    status = Column(String(64), default="ACTIVE")
    created_at = Column(DateTime, server_default=func.now())

    golden_customer = relationship("GoldenCustomer", foreign_keys=[golden_customer_id])


class ConfigEntry(Base):
    __tablename__ = "config_entries"
    id = Column(Integer, primary_key=True)
    category = Column(Enum(ConfigCategoryEnum), nullable=False)
    key = Column(String(256), nullable=False)
    value = Column(JSON_TYPE, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    updated_by_user = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        UniqueConstraint("category", "key", name="uix_config_category_key"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(128), nullable=False)
    entity_id = Column(String(128), nullable=True)
    before_value = Column(JSON_TYPE, nullable=True)
    after_value = Column(JSON_TYPE, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    actor = relationship("User", foreign_keys=[actor_id])
