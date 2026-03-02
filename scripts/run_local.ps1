$ErrorActionPreference = 'Stop'

$env:DATABASE_URL = 'sqlite:///./app.db'
$env:REDIS_URL = 'redis://localhost:6379/0'

python -c "import app.db.models; from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine); print('db ready')"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
