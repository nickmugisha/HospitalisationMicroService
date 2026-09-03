from __future__ import annotations

import grpc
from common.v1 import common_pb2
from services.common.health_compat import health_category, health_status_name
from auth.v1 import auth_pb2_grpc
from accueil.v1 import accueil_pb2_grpc
from hospitalisation.v1 import hospitalisation_pb2_grpc
from billing.v1 import billing_pb2_grpc
from consultation.v1 import consultation_pb2_grpc
from laboratoire.v1 import laboratoire_pb2_grpc
from pharmacie.v1 import pharmacie_pb2_grpc
from maternite.v1 import maternite_pb2_grpc
from rendezvous.v1 import rendezvous_pb2_grpc
from bi.v1 import bi_pb2_grpc
from chatbot.v1 import chatbot_pb2_grpc
from hr.v1 import hr_pb2_grpc

SPECS = [
    ("auth", 50051, auth_pb2_grpc.AuthServiceStub),
    ("accueil", 50052, accueil_pb2_grpc.AccueilServiceStub),
    ("hospitalisation", 50053, hospitalisation_pb2_grpc.HospitalisationServiceStub),
    ("billing", 50054, billing_pb2_grpc.BillingServiceStub),
    ("consultation", 50055, consultation_pb2_grpc.ConsultationServiceStub),
    ("laboratoire", 50056, laboratoire_pb2_grpc.LaboratoireServiceStub),
    ("pharmacie", 50057, pharmacie_pb2_grpc.PharmacieServiceStub),
    ("maternite", 50058, maternite_pb2_grpc.MaterniteServiceStub),
    ("rendezvous", 50059, rendezvous_pb2_grpc.RendezvousServiceStub),
    ("bi", 50060, bi_pb2_grpc.BIServiceStub),
    ("chatbot", 50061, chatbot_pb2_grpc.ChatbotServiceStub),
    ("hr", 50062, hr_pb2_grpc.HRServiceStub),
]

failed = []
print("PROJECTX GLOBAL HEALTH")
print("======================")
for name, port, stub_cls in SPECS:
    try:
        with grpc.insecure_channel(f"127.0.0.1:{port}") as ch:
            response = stub_cls(ch).HealthCheck(common_pb2.HealthRequest(), timeout=4)
        status = health_status_name(response)
        category = health_category(response)
        message = getattr(response, "message", "")
        print(f"{port} {name:<16} {status:<36} [{category}] {message}")
        if category != "ONLINE":
            failed.append(name)
    except grpc.RpcError as exc:
        print(f"{port} {name:<16} ERROR {exc.code().name}: {exc.details()}")
        failed.append(name)

print("======================")
print("Services online:", len(SPECS) - len(failed), "/", len(SPECS))
if failed:
    print("Not fully online:", failed)
    raise SystemExit(1)
print("PROJECTX ALL 12 SERVICES ONLINE (v2.1 incl. HR extension)")
