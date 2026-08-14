from __future__ import annotations

import getpass
from datetime import datetime, timezone

import grpc

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc


def metadata(token: str):
    return (("authorization", f"Bearer {token}"),)


def main():
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    with grpc.insecure_channel("127.0.0.1:50051") as auth_channel:
        auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
        login = auth_stub.Login(
            auth_pb2.LoginRequest(username=username, password=password),
            timeout=5,
        )

    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")[-10:]
    with grpc.insecure_channel("127.0.0.1:50052") as channel:
        stub = accueil_pb2_grpc.AccueilServiceStub(channel)
        patient_response = stub.CreatePatient(
            accueil_pb2.CreatePatientRequest(
                first_name="Test",
                last_name=f"Patient{stamp}",
                sex=accueil_pb2.SEX_MALE,
                birth_date="1995-01-01",
                phone=f"+25779{stamp}",
                address="Bujumbura",
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        )
        patient = patient_response.patient

        search = stub.SearchPatients(
            accueil_pb2.SearchPatientsRequest(query=patient.patient_number, limit=20),
            metadata=metadata(login.access_token),
            timeout=5,
        )

        arrival = stub.RegisterArrival(
            accueil_pb2.RegisterArrivalRequest(
                patient_id=patient.id,
                reason="Consultation générale",
                target_service="CONSULTATION",
                priority=accueil_pb2.ARRIVAL_PRIORITY_ROUTINE,
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).arrival

        queue = stub.ListWaitingQueue(
            accueil_pb2.ListWaitingQueueRequest(target_service="CONSULTATION", limit=20),
            metadata=metadata(login.access_token),
            timeout=5,
        )

    print()
    print("================================")
    print(" PROJECTX ACCUEIL SMOKE SUCCESS")
    print("================================")
    print("Patient number :", patient.patient_number)
    print("Search results :", search.total)
    print("Arrival status :", accueil_pb2.ArrivalStatus.Name(arrival.status))
    print("Queue total    :", queue.total)
    print("JWT printed    : False")


if __name__ == "__main__":
    try:
        main()
    except grpc.RpcError as error:
        print("PROJECTX ACCUEIL SMOKE FAILED")
        print("STATUS :", error.code().name)
        print("DETAIL :", error.details())
