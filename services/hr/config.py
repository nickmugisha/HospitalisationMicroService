import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import URL

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

MYSQL_HOST = required_env("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = required_env("MYSQL_USER")
MYSQL_PASSWORD = required_env("MYSQL_PASSWORD")
MYSQL_HR_DATABASE = os.getenv("MYSQL_HR_DATABASE", "hospital_hr")
DATABASE_URL = URL.create(drivername="mysql+pymysql", username=MYSQL_USER, password=MYSQL_PASSWORD,
                          host=MYSQL_HOST, port=MYSQL_PORT, database=MYSQL_HR_DATABASE,
                          query={"charset": "utf8mb4"})
HR_GRPC_HOST = os.getenv("HR_GRPC_HOST", "0.0.0.0")
HR_GRPC_PORT = int(os.getenv("HR_GRPC_PORT", "50062"))
AUTH_GRPC_TARGET = os.getenv("AUTH_GRPC_TARGET", "127.0.0.1:50051")
SERVICE_VERSION = os.getenv("PROJECTX_SERVICE_VERSION", "2.1.0")
HR_LOCAL_UTC_OFFSET_MINUTES = int(os.getenv("HR_LOCAL_UTC_OFFSET_MINUTES", "120"))
HR_LATE_GRACE_MINUTES = int(os.getenv("HR_LATE_GRACE_MINUTES", "15"))
