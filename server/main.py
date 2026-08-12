from concurrent import futures

import grpc

import hospital_pb2
import hospital_pb2_grpc


class HospitalSystemService(
    hospital_pb2_grpc.HospitalSystemServiceServicer
):

    def HealthCheck(self, request, context):
        print()
        print("==============================================")
        print("           NOUVELLE REQUETE gRPC")
        print("==============================================")
        print(f"Client      : {request.client_name}")
        print(f"Peer réseau : {context.peer()}")
        print("RPC         : HealthCheck")
        print("==============================================")

        return hospital_pb2.HealthResponse(
            success=True,
            status="ONLINE",
            server_name="ProjectX Windows Server",
            message=(
                f"Connexion gRPC réussie avec "
                f"{request.client_name}"
            ),
        )

    def SayHello(self, request, context):
        print()
        print("----------------------------------------------")
        print("RPC SayHello reçu")
        print(f"Nom  : {request.name}")
        print(f"Peer : {context.peer()}")
        print("----------------------------------------------")

        return hospital_pb2.HelloResponse(
            message=(
                f"Bonjour {request.name}! "
                f"Le serveur ProjectX Windows répond via gRPC."
            )
        )


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=20)
    )

    hospital_pb2_grpc.add_HospitalSystemServiceServicer_to_server(
        HospitalSystemService(),
        server,
    )

    server.add_insecure_port("[::]:50051")

    server.start()

    print()
    print("====================================================")
    print("             PROJECTX gRPC SERVER")
    print("====================================================")
    print(" OS       : Windows")
    print(" Role     : SERVER")
    print(" Protocol : gRPC")
    print(" Port     : 50051")
    print(" Listen   : 0.0.0.0 / all interfaces")
    print(" Status   : ONLINE")
    print("====================================================")
    print()
    print("En attente du client Linux...")
    print()

    server.wait_for_termination()


if __name__ == "__main__":
    serve()