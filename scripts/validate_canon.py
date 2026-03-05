from app.canon.validate import validate_canon_integrity
from app.db.session import SessionLocal

if __name__ == "__main__":
    with SessionLocal() as db:
        report = validate_canon_integrity(db)
    if report.ok:
        print("canon validation passed")
        raise SystemExit(0)
    print("canon validation failed:")
    for err in report.errors:
        print("-", err)
    raise SystemExit(1)
