from __future__ import annotations

import grpc

from auth.v1 import auth_pb2
from auth.v1 import auth_pb2_grpc


def main():
    channel = grpc.insecure_channel(
        "127.0.0.1:50051"
    )

    stub = auth_pb2_grpc.AuthServiceStub(
        channel
    )

    try:
        response = stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(
                access_token="this-is-not-a-valid-projectx-jwt",
            ),
            timeout=5,
        )

        print()
        print("================================")
        print(" PROJECTX INVALID TOKEN TEST")
        print("================================")
        print("Valid:", response.valid)

        if response.valid:
            print("ERROR: invalid token was accepted!")
        else:
            print("INVALID TOKEN CORRECTLY REJECTED")

    except grpc.RpcError as error:
        print("gRPC ERROR")
        print("STATUS:", error.code().name)
        print("DETAIL:", error.details())

    finally:
        channel.close()


if __name__ == "__main__":
    main()