import grpc

import hospital_pb2
import hospital_pb2_grpc


SERVER_IP = "10.139.91.95"
SERVER_PORT = 50051


def main():
    address = f"{SERVER_IP}:{SERVER_PORT}"

    print()
    print("====================================================")
    print("             PROJECTX gRPC CLIENT")
    print("====================================================")
    print(" OS       : Linux")
    print(" Role     : CLIENT")
    print(" Protocol : gRPC")
    print(f" Server   : {address}")
    print("====================================================")
    print()
    print("Connexion au serveur Windows...")

    channel = grpc.insecure_channel(address)

    try:
        grpc.channel_ready_future(channel).result(timeout=5)

        stub = hospital_pb2_grpc.HospitalSystemServiceStub(channel)

        response = stub.HealthCheck(
            hospital_pb2.HealthRequest(
                client_name="Kenny Linux Client"
            ),
            timeout=5
        )

        print()
        print("✅ CONNEXION gRPC REUSSIE")
        print("Status  :", response.status)
        print("Serveur :", response.server_name)
        print("Message :", response.message)

        hello = stub.SayHello(
            hospital_pb2.HelloRequest(
                name="Kenny Love"
            ),
            timeout=5
        )

        print()
        print("✅ RPC SAYHELLO REUSSI")
        print(hello.message)

    except grpc.FutureTimeoutError:
        print()
        print("❌ Impossible de joindre le serveur gRPC.")

    except grpc.RpcError as error:
        print()
        print("❌ Erreur gRPC")
        print("Code    :", error.code())
        print("Message :", error.details())

    finally:
        channel.close()


if __name__ == "__main__":
    main()
