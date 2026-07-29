from app.db.sqlite_db import init_db
from app.services.discovery_service import run_job_discovery

if __name__ == "__main__":
    init_db()
    summary = run_job_discovery()
    print(f"Processed {summary.get('processed_total', 0)} jobs.")