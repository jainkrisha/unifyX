"""Bootstrap script to ensure the database is present and seed config."""
import sqlite3
from src.db.session import SessionLocal
from src.seed_config import seed_config

# Check what tables exist
conn = sqlite3.connect('unifyx.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"✓ Existing tables: {', '.join([t[0] for t in tables])}")
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
