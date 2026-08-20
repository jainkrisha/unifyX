"""Create, seed, ingest, and match the local development database."""
from src.db.models import (
    AuditLog,
    ConfigEntry,
    CustomerLink,
    FieldProvenance,
    GoldenCustomer,
    Opportunity,
    ReviewQueueItem,
    SourceRecord,
    User,
)
from src.db.session import Base, SessionLocal, engine
from src.auth.jwt import hash_password
from src.db.models import RoleEnum
from src.ingest import ingest_all
from src.pipeline.match import run_match_pipeline
from src.seed_config import seed_config

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    seed_config(db)

    manager = db.query(User).filter(User.email == "manager@unifyx.com").first()
    if manager is None:
        manager = User(
            email="manager@unifyx.com",
            password_hash=hash_password("manager123"),
            role=RoleEnum.MANAGER,
        )
        db.add(manager)
        db.flush()

    users = [
        ("admin@unifyx.com", "admin123", RoleEnum.ADMIN, None),
        ("rm1@unifyx.com", "rm123", RoleEnum.RM, manager.id),
        ("rm2@unifyx.com", "rm123", RoleEnum.RM, manager.id),
    ]
    for email, password, role, manager_id in users:
        if db.query(User).filter(User.email == email).first() is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                    manager_id=manager_id,
                )
            )
    db.commit()
finally:
    db.close()

ingest_summary = ingest_all()
db = SessionLocal()
try:
    pipeline_summary = run_match_pipeline(db)
    counts = {
        model.__tablename__: db.query(model).count()
        for model in (
            User,
            SourceRecord,
            GoldenCustomer,
            CustomerLink,
            FieldProvenance,
            ReviewQueueItem,
            Opportunity,
            ConfigEntry,
            AuditLog,
        )
    }
finally:
    db.close()

print("Ingestion summary:", ingest_summary)
print("Pipeline summary:", pipeline_summary)
print("Final row counts:")
for table_name, row_count in counts.items():
    print(f"  {table_name}: {row_count}")
