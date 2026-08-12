import os
import sys
from pathlib import Path

import grpc
from dotenv import load_dotenv


# ---------------------------------------------------------
# ROOT PROJECT
# ---------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[3]
GENERATED_DIR = ROOT_DIR / "generated"

if str(GENERATED_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATED_DIR))


import hospital_pb2
import hospital_pb2_grpc


load_dotenv(ROOT_DIR / ".env")


GRPC_SERVER_HOST = os.getenv(
    "GRPC_SERVER_HOST",
    "10.139.91.95"
)

GRPC_SERVER_PORT = int(
    os.getenv(
        "GRPC_SERVER_PORT",
        "50051"
    )
)


class HospitalGrpcClient:

    def __init__(self):
        self.target = (
            f"{GRPC_SERVER_HOST}:{GRPC_SERVER_PORT}"
        )

    def health_check(self):
        channel = grpc.insecure_channel(self.target)

        try:
            grpc.channel_ready_future(
                channel
            ).result(timeout=3)

            stub = (
                hospital_pb2_grpc
                .HospitalSystemServiceStub(channel)
            )

            response = stub.HealthCheck(
                hospital_pb2.HealthRequest(
                    client_name="Hospital React/FastAPI Client"
                ),
                timeout=5
            )

            return {
                "online": True,
                "status": response.status,
                "server_name": response.server_name,
                "message": response.message,
                "target": self.target,
            }

        except grpc.FutureTimeoutError:
            return {
                "online": False,
                "status": "OFFLINE",
                "server_name": None,
                "message": "Le serveur gRPC est inaccessible.",
                "target": self.target,
            }

        except grpc.RpcError as error:
            return {
                "online": False,
                "status": "ERROR",
                "server_name": None,
                "message": error.details() or "Erreur gRPC",
                "grpc_code": error.code().name,
                "target": self.target,
            }

        finally:
            channel.close()


hospital_grpc_client = HospitalGrpcClient()
