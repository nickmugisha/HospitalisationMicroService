import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


MYSQL_HOST = required_env("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = required_env("MYSQL_USER")
MYSQL_PASSWORD = required_env("MYSQL_PASSWORD")
MYSQL_PHARMACIE_DATABASE = os.getenv("MYSQL_PHARMACIE_DATABASE", "hospital_pharmacie")

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=MYSQL_USER,
    password=MYSQL_PASSWORD,
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    database=MYSQL_PHARMACIE_DATABASE,
    query={"charset": "utf8mb4"},
)

PHARMACIE_GRPC_HOST = os.getenv("PHARMACIE_GRPC_HOST", "0.0.0.0")
PHARMACIE_GRPC_PORT = int(os.getenv("PHARMACIE_GRPC_PORT", "50057"))
AUTH_GRPC_TARGET = os.getenv("AUTH_GRPC_TARGET", "127.0.0.1:50051")
BILLING_GRPC_TARGET = os.getenv("BILLING_GRPC_TARGET", "127.0.0.1:50054")
SERVICE_VERSION = os.getenv("PROJECTX_SERVICE_VERSION", "1.0.0")

PHARMACIE_ALERT_POLL_SECONDS = int(os.getenv("PHARMACIE_ALERT_POLL_SECONDS", "3600"))
PHARMACIE_ALERT_EXPIRY_DAYS = int(os.getenv("PHARMACIE_ALERT_EXPIRY_DAYS", "30"))
