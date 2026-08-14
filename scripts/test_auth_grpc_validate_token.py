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
        # 1. Login
        login_response = stub.Login(
            auth_pb2.LoginRequest(
                username=username,
                password=password,
            ),
            timeout=5,
        )

        print()
        print("LOGIN OK")
        print(
            "JWT received:",
            bool(login_response.access_token),
        )

        # 2. Validate the JWT returned by Login
        validation = stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(
                access_token=login_response.access_token,
            ),
            timeout=5,
        )

        print()
        print("================================")
        print(" PROJECTX TOKEN VALIDATION")
        print("================================")
        print("Valid       :", validation.valid)

        if validation.valid:
            print(
                "User        :",
                validation.user.username,
            )
            print(
                "Display name:",
                validation.user.display_name,
            )
            print(
                "Roles       :",
                list(validation.user.roles),
            )
            print(
                "Permissions :",
                len(validation.user.permissions),
            )

    except grpc.RpcError as error:
        print()
        print("PROJECTX TOKEN TEST FAILED")
        print(
            "STATUS :",
            error.code().name,
        )
        print(
            "DETAIL :",
            error.details(),
        )

    finally:
        channel.close()


if __name__ == "__main__":
    main()