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
MYSQL_CHATBOT_DATABASE = os.getenv("MYSQL_CHATBOT_DATABASE", "hospital_chatbot")
DATABASE_URL = URL.create(
    drivername="mysql+pymysql", username=MYSQL_USER, password=MYSQL_PASSWORD,
    host=MYSQL_HOST, port=MYSQL_PORT, database=MYSQL_CHATBOT_DATABASE,
    query={"charset": "utf8mb4"},
)

CHATBOT_GRPC_HOST = os.getenv("CHATBOT_GRPC_HOST", "0.0.0.0")
CHATBOT_GRPC_PORT = int(os.getenv("CHATBOT_GRPC_PORT", "50061"))
AUTH_GRPC_TARGET = os.getenv("AUTH_GRPC_TARGET", "127.0.0.1:50051")
ACCUEIL_GRPC_TARGET = os.getenv("ACCUEIL_GRPC_TARGET", "127.0.0.1:50052")
HOSPITALISATION_GRPC_TARGET = os.getenv("HOSPITALISATION_GRPC_TARGET", "127.0.0.1:50053")
BILLING_GRPC_TARGET = os.getenv("BILLING_GRPC_TARGET", "127.0.0.1:50054")
PHARMACIE_GRPC_TARGET = os.getenv("PHARMACIE_GRPC_TARGET", "127.0.0.1:50057")
RENDEZVOUS_GRPC_TARGET = os.getenv("RENDEZVOUS_GRPC_TARGET", "127.0.0.1:50059")
BI_GRPC_TARGET = os.getenv("BI_GRPC_TARGET", "127.0.0.1:50060")
SERVICE_VERSION = os.getenv("PROJECTX_SERVICE_VERSION", "1.0.0")
