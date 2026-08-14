from __future__ import annotations

import logging
from concurrent import futures

import grpc

from billing.v1 import billing_pb2_grpc
from services.billing.config import BILLING_GRPC_HOST, BILLING_GRPC_PORT
from services.billing.service import BillingService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("projectx.billing")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=12))
    billing_pb2_grpc.add_BillingServiceServicer_to_server(BillingService(), server)
    address = f"{BILLING_GRPC_HOST}:{BILLING_GRPC_PORT}"
    bound_port = server.add_insecure_port(address)
    if bound_port == 0:
        raise RuntimeError(f"Unable to bind BillingService to {address}")
    server.start()
    logger.info("PROJECTX BillingService started on %s", address)
    logger.info("Billing gRPC port: %s", bound_port)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX BillingService...")
        server.stop(grace=5)
        logger.info("PROJECTX BillingService stopped.")


if __name__ == "__main__":
    serve()
