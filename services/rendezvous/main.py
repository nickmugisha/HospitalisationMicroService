from __future__ import annotations
import logging
import threading
import time
from concurrent import futures
import grpc
from rendezvous.v1 import rendezvous_pb2_grpc
from services.rendezvous.config import RENDEZVOUS_GRPC_HOST, RENDEZVOUS_GRPC_PORT, RENDEZVOUS_REMINDER_POLL_SECONDS
from services.rendezvous.service import RendezvousService, dispatch_due_reminders_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger=logging.getLogger("projectx.rendezvous")

def reminder_worker():
    interval=max(15, min(int(RENDEZVOUS_REMINDER_POLL_SECONDS), 3600))
    while True:
        try:
            sent,failed=dispatch_due_reminders_once()
            if sent or failed: logger.info("appointment reminder worker sent=%s failed=%s",sent,failed)
        except Exception:
            logger.exception("appointment reminder worker iteration failed")
        time.sleep(interval)

def serve() -> None:
    server=grpc.server(futures.ThreadPoolExecutor(max_workers=12))
    rendezvous_pb2_grpc.add_RendezvousServiceServicer_to_server(RendezvousService(),server)
    address=f"{RENDEZVOUS_GRPC_HOST}:{RENDEZVOUS_GRPC_PORT}"
    bound_port=server.add_insecure_port(address)
    if bound_port==0: raise RuntimeError(f"Unable to bind RendezvousService to {address}")
    server.start(); logger.info("PROJECTX RendezvousService started on %s",address); logger.info("Rendezvous gRPC port: %s",bound_port)
    threading.Thread(target=reminder_worker,name="projectx-rendezvous-reminders",daemon=True).start()
    try: server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX RendezvousService..."); server.stop(grace=5); logger.info("PROJECTX RendezvousService stopped.")

if __name__=="__main__": serve()
