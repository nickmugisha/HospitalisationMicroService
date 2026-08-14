from __future__ import annotations

import getpass

import grpc

from auth.v1 import auth_pb2
from auth.v1 import auth_pb2_grpc


def main():
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    channel = grpc.insecure_channel(
        "127.0.0.1:50051"
    )

    stub = auth_pb2_grpc.AuthServiceStub(
        channel
    )

    try:
        response = stub.Login(
            auth_pb2.LoginRequest(
                username=username,
                password=password,
            ),
            timeout=5,
        )

        print()
        print("================================")
        print(" PROJECTX gRPC LOGIN SUCCESS")
        print("================================")
        print("User        :", response.user.username)
        print("Display name:", response.user.display_name)
        print("Roles       :", list(response.user.roles))
        print(
            "Permissions :",
            len(response.user.permissions),
        )
        print(
            "JWT received:",
            bool(response.access_token),
        )

    except grpc.RpcError as error:
        print()
        print("PROJECTX gRPC LOGIN FAILED")
        print("STATUS :", error.code().name)
        print("DETAIL :", error.details())

    finally:
        channel.close()


if __name__ == "__main__":
    main()