import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL


ROOT_DIR = Path(__file__).resolve().parents[2]

load_dotenv(ROOT_DIR / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


PROJECTX_ENV = os.getenv(
    "PROJECTX_ENV",
    "development",
)

MYSQL_HOST = required_env("MYSQL_HOST")
MYSQL_PORT = int(
    os.getenv("MYSQL_PORT", "3306")
)
MYSQL_USER = required_env("MYSQL_USER")
MYSQL_PASSWORD = required_env("MYSQL_PASSWORD")
MYSQL_AUTH_DATABASE = required_env(
    "MYSQL_AUTH_DATABASE"
)


DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=MYSQL_USER,
    password=MYSQL_PASSWORD,
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    database=MYSQL_AUTH_DATABASE,
    query={
        "charset": "utf8mb4",
    },
)


JWT_SECRET = required_env("JWT_SECRET")
JWT_ALGORITHM = os.getenv(
    "JWT_ALGORITHM",
    "HS256",
)
JWT_EXPIRATION_MINUTES = int(
    os.getenv(
        "JWT_EXPIRATION_MINUTES",
        "480",
    )
)


AUTH_GRPC_HOST = os.getenv(
    "AUTH_GRPC_HOST",
    "0.0.0.0",
)

AUTH_GRPC_PORT = int(
    os.getenv(
        "AUTH_GRPC_PORT",
        "50051",
    )
)