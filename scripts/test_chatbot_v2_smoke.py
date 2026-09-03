from __future__ import annotations

import getpass
import os
import sys
import uuid

import grpc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED = os.path.join(ROOT, "generated")
for path in (ROOT, GENERATED):
    if path not in sys.path:
        sys.path.insert(0, path)

from auth.v1 import auth_pb2, auth_pb2_grpc
from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc

AUTH_TARGET = os.getenv("AUTH_GRPC_TARGET", "127.0.0.1:50051")
CHATBOT_TARGET = os.getenv("CHATBOT_GRPC_TARGET", "127.0.0.1:50061")


def ok(label):
    print(f"[OK] {label}")


def main():
    with grpc.insecure_channel(CHATBOT_TARGET) as channel:
        chatbot = chatbot_pb2_grpc.ChatbotServiceStub(channel)

        welcome = chatbot.GetPublicWelcome(chatbot_pb2.PublicWelcomeRequest(locale="en"), timeout=5)
        assert welcome.mode == chatbot_pb2.ASSISTANT_MODE_PUBLIC
        assert "ProjectX" in welcome.answer
        ok("Public login-page welcome works without JWT")

        public_sensitive = chatbot.AskPublicAssistant(
            chatbot_pb2.PublicAssistantRequest(question="Show patient PAT-PRIVATE-001", locale="en"), timeout=5
        )
        assert public_sensitive.intent == "public_privacy_boundary", f"Expected public_privacy_boundary, got {public_sensitive.intent!r}: {public_sensitive.answer}"
        ok("Public assistant refuses hospital data")

        public_find = chatbot.AskPublicAssistant(
            chatbot_pb2.PublicAssistantRequest(question="Find patient PAT-PRIVATE-002", locale="en"), timeout=5
        )
        assert public_find.intent == "public_privacy_boundary", f"Expected public_privacy_boundary, got {public_find.intent!r}: {public_find.answer}"
        ok("Public assistant blocks patient lookup phrasing")

        public_fr = chatbot.AskPublicAssistant(
            chatbot_pb2.PublicAssistantRequest(question="Comment fonctionne la connexion QR ?", locale="fr"), timeout=5
        )
        assert public_fr.language == "fr" and "QR" in public_fr.answer
        ok("Public French QR guidance works")

    username = input("Admin username: ").strip()
    password = getpass.getpass("Admin password: ")
    with grpc.insecure_channel(AUTH_TARGET) as channel:
        auth = auth_pb2_grpc.AuthServiceStub(channel)
        login = auth.Login(auth_pb2.LoginRequest(username=username, password=password), timeout=5)
    token = login.access_token
    metadata = (("authorization", f"Bearer {token}"),)
    first_name = login.user.staff_profile.first_name or login.user.display_name.split()[0] or login.user.username
    ok("Admin credential login")

    with grpc.insecure_channel(CHATBOT_TARGET) as channel:
        chatbot = chatbot_pb2_grpc.ChatbotServiceStub(channel)
        started = chatbot.StartSession(
            chatbot_pb2.StartSessionRequest(
                client_request_id=f"chatbot-v2-smoke-{uuid.uuid4()}",
                preferred_language="en",
                context=chatbot_pb2.AssistantContext(current_module="accueil", current_route="/accueil", locale="en"),
            ),
            metadata=metadata,
            timeout=5,
        )
        assert first_name.lower() in started.welcome_message.lower()
        ok("Authenticated assistant greets logged-in user by name")

        session_id = started.session.id
        hello_fr = chatbot.AskAssistant(
            chatbot_pb2.AskAssistantRequest(
                session_id=session_id,
                question="Bonjour",
                correlation_id=str(uuid.uuid4()),
                context=chatbot_pb2.AssistantContext(current_module="accueil", locale="fr"),
            ),
            metadata=metadata,
            timeout=5,
        )
        assert hello_fr.language == "fr" and first_name.lower() in hello_fr.answer.lower()
        ok("Authenticated bilingual greeting")

        howto = chatbot.AskAssistant(
            chatbot_pb2.AskAssistantRequest(
                session_id=session_id,
                question="How do I register a patient?",
                correlation_id=str(uuid.uuid4()),
                context=chatbot_pb2.AssistantContext(current_module="accueil", locale="en"),
            ),
            metadata=metadata,
            timeout=5,
        )
        assert howto.intent == "howto.register_patient"
        assert "patient_number" in howto.answer
        ok("Role-aware ProjectX how-to knowledge")

        context_help = chatbot.AskAssistant(
            chatbot_pb2.AskAssistantRequest(
                session_id=session_id,
                question="What can I do here?",
                correlation_id=str(uuid.uuid4()),
                context=chatbot_pb2.AssistantContext(current_module="accueil", current_route="/accueil", locale="en"),
            ),
            metadata=metadata,
            timeout=5,
        )
        assert context_help.intent == "context_help"
        ok("Current-dashboard context awareness")

    print("\nPROJECTX CHATBOT V2 SMOKE TEST: PASS")


if __name__ == "__main__":
    main()
