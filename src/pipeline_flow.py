import subprocess
import sys
from pathlib import Path
from prefect import flow, task, get_run_logger
from prefect.schedules import Interval
from datetime import timedelta

# Absolute paths so Prefect can find everything regardless of where it runs from
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON  = PROJECT_ROOT / "venv/bin/python"
INGESTION    = PROJECT_ROOT / "src/ingestion"
DBT_PROJECT  = PROJECT_ROOT / "src/dbt_project/crypto_pipeline"

# ── @task means Prefect tracks this step individually ─────────────────────────
# If it fails, Prefect marks just this task red — not the whole flow

@task(name="Ingest Crypto Prices", retries=2, retry_delay_seconds=30)
def ingest_crypto():
    logger = get_run_logger()
    logger.info("Starting crypto ingestion...")
    result = subprocess.run(
        [str(VENV_PYTHON), str(INGESTION / "ingest.py")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception(f"Crypto ingestion failed:\n{result.stderr}")
    logger.info(result.stdout.strip())

@task(name="Ingest Stock Prices", retries=2, retry_delay_seconds=30)
def ingest_stocks():
    logger = get_run_logger()
    logger.info("Starting stock ingestion...")
    result = subprocess.run(
        [str(VENV_PYTHON), str(INGESTION / "ingest_stocks.py")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception(f"Stock ingestion failed:\n{result.stderr}")
    logger.info(result.stdout.strip())

@task(name="Run dbt Transformations")
def run_dbt():
    logger = get_run_logger()
    logger.info("Running dbt transformations...")
    result = subprocess.run(
        ["dbt", "run"],
        capture_output=True, text=True,
        cwd=str(DBT_PROJECT)
    )
    if result.returncode != 0:
        raise Exception(f"dbt run failed:\n{result.stderr}\n{result.stdout}")
    logger.info(result.stdout.strip())

@task(name="Run dbt Tests")
def run_dbt_tests():
    logger = get_run_logger()
    logger.info("Running dbt tests...")
    result = subprocess.run(
        ["dbt", "test"],
        capture_output=True, text=True,
        cwd=str(DBT_PROJECT)
    )
    if result.returncode != 0:
        raise Exception(f"dbt tests failed:\n{result.stderr}\n{result.stdout}")
    logger.info(result.stdout.strip())

# ── @flow is the orchestrator — runs tasks in order ───────────────────────────
@flow(
    name="Lakehouse Pipeline",
    description="Ingest crypto + stocks, transform with dbt, validate with tests"
)
def lakehouse_pipeline():
    logger = get_run_logger()
    logger.info("Pipeline started")

    # These run sequentially — each must succeed before the next starts
    ingest_crypto()
    ingest_stocks()
    run_dbt()
    run_dbt_tests()

    logger.info("Pipeline completed successfully")

# ── Run manually or on schedule ───────────────────────────────────────────────
if __name__ == "__main__":
    lakehouse_pipeline.serve(
        name="hourly-lakehouse-run",
        interval=timedelta(hours=1)
    )