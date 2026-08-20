"""Bootstrap script to create database tables and seed config."""
import sqlite3
from src.db.session import engine, Base
from src.db.models import *
from src.seed_config import seed_config, SessionLocal

print("Creating database tables...")
Base.metadata.create_all(bind=engine)

# Check what tables exist
conn = sqlite3.connect('unifyx.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"✓ Tables created: {', '.join([t[0] for t in tables])}")
conn.close()

print("\nSeeding configuration...")
db = SessionLocal()
try:
    seed_config(db)
    print("✓ Configuration seeding complete")
except Exception as e:
    print(f"✗ Error seeding config: {e}")
    db.rollback()
finally:
    db.close()

print("\n✓ All done! Database is ready for Phase 2")
