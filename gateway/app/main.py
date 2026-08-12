import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from gateway.app.grpc_clients.system_client import hospital_grpc_client


load_dotenv()

app = FastAPI(
    title="Hospitalisation MicroService Client Gateway",
    description=(
        "Gateway HTTP local du client React "
        "vers les microservices gRPC distants."
    ),
    version="1.0.0",
)

frontend_origin = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:5173",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_origin,
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Correlation-ID",
        "X-Client-Version",
    ],
)


@app.get("/")
def root():
    return {
        "application": "Hospitalisation MicroService",
        "role": "CLIENT",
        "os": "Linux",
        "gateway": "ONLINE",
        "protocol_to_server": "gRPC",
    }


@app.get("/api/system/health")
def system_health():
    return hospital_grpc_client.health_check()
