from app.canon.ingest import main as ingest_main
from app.canon.validate import validate_canon_integrity
from app.db.session import SessionLocal

if __name__ == "__main__":
    ingest_main()
    with SessionLocal() as db:
        report = validate_canon_integrity(db)
    if not report.ok:
        raise SystemExit(f"canon validation failed: {report.errors}")
    print("canon validation passed")
