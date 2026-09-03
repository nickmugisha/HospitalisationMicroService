from __future__ import annotations

import getpass
import os
import sys
import uuid
from dataclasses import dataclass

import grpc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED = os.path.join(ROOT, "generated")
for path in (ROOT, GENERATED):
    if path not in sys.path:
        sys.path.insert(0, path)

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc
from bi.v1 import bi_pb2, bi_pb2_grpc
from maternite.v1 import maternite_pb2, maternite_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc

AUTH_TARGET = os.getenv("AUTH_GRPC_TARGET", "127.0.0.1:50051")
ACCUEIL_TARGET = os.getenv("ACCUEIL_GRPC_TARGET", "127.0.0.1:50052")
PHARMACIE_TARGET = os.getenv("PHARMACIE_GRPC_TARGET", "127.0.0.1:50057")
MATERNITE_TARGET = os.getenv("MATERNITE_GRPC_TARGET", "127.0.0.1:50058")
BI_TARGET = os.getenv("BI_GRPC_TARGET", "127.0.0.1:50060")
CHATBOT_TARGET = os.getenv("CHATBOT_GRPC_TARGET", "127.0.0.1:50061")


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""


RESULTS: list[Result] = []


def record(name: str, status: str, detail: str = ""):
    RESULTS.append(Result(name, status, detail))
    prefix = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
    print(f"{prefix} {name}" + (f" — {detail}" if detail else ""))


def md(token: str):
    return (("authorization", f"Bearer {token}"),)


def ask(stub, token: str, session_id: str, question: str, language: str = "en", module: str = "general",
        patient_id: str = "", patient_number: str = ""):
    return stub.AskAssistant(
        chatbot_pb2.AskAssistantRequest(
            session_id=session_id,
            question=question,
            correlation_id=str(uuid.uuid4()),
            context=chatbot_pb2.AssistantContext(
                current_module=module,
                current_route=f"/{module}" if module != "general" else "/",
                active_patient_id=patient_id,
                active_patient_number=patient_number,
                locale=language,
            ),
        ),
        metadata=md(token),
        timeout=15,
    )


def assert_live(name: str, response, expected_intent: str, expected_service: str, allow_safe_negative: bool = False):
    if response.intent != expected_intent:
        record(name, "FAIL", f"expected intent={expected_intent}, got intent={response.intent}; answer={response.answer[:180]!r}")
        return False
    matching = [s for s in response.sources if s.service == expected_service]
    if not matching:
        record(name, "FAIL", f"intent matched but no source from {expected_service}; sources={[s.service for s in response.sources]}")
        return False
    if any(s.success for s in matching):
        record(name, "PASS", f"{expected_intent} → {expected_service}; {response.answer[:140]}")
        return True
    if allow_safe_negative:
        record(name, "WARN", f"routing/security path exercised but downstream returned a safe failure: {matching[0].message}")
        return False
    record(name, "FAIL", f"downstream {expected_service} failed: {matching[0].message}")
    return False


def discover_patients(token: str, limit: int = 300):
    found = []
    with grpc.insecure_channel(ACCUEIL_TARGET) as channel:
        stub = accueil_pb2_grpc.AccueilServiceStub(channel)
        offset = 0
        while len(found) < limit:
            batch = stub.SearchPatients(
                accueil_pb2.SearchPatientsRequest(query="", limit=min(100, limit - len(found)), offset=offset),
                metadata=md(token), timeout=5,
            )
            found.extend(batch.patients)
            offset += len(batch.patients)
            if not batch.patients or offset >= batch.total:
                break
    return found


def discover_maternity_patient(token: str, patients):
    with grpc.insecure_channel(MATERNITE_TARGET) as channel:
        stub = maternite_pb2_grpc.MaterniteServiceStub(channel)
        for patient in patients:
            try:
                stub.GetMaternityRecord(
                    maternite_pb2.GetMaternityRecordRequest(patient_id=patient.id),
                    metadata=md(token), timeout=2,
                )
                return patient
            except grpc.RpcError as exc:
                if exc.code() == grpc.StatusCode.NOT_FOUND:
                    continue
                # A permission/network problem is important; let the caller see it.
                raise
    return None


def discover_medicine(token: str):
    with grpc.insecure_channel(PHARMACIE_TARGET) as channel:
        stub = pharmacie_pb2_grpc.PharmacieServiceStub(channel)
        result = stub.SearchMedicines(
            pharmacie_pb2.SearchMedicinesRequest(query="", active_only=True, limit=50, offset=0),
            metadata=md(token), timeout=5,
        )
        return result.medicines[0] if result.medicines else None


def main():
    print("PROJECTX CHATBOT V2 — FULL E2E VERIFICATION")
    print("===========================================")
    print("This suite is intentionally non-destructive for hospital business data.")
    print("It performs live READS only. Chatbot test sessions are cleared at the end.\n")

    # 1) Public/login-page boundary.
    with grpc.insecure_channel(CHATBOT_TARGET) as channel:
        chatbot = chatbot_pb2_grpc.ChatbotServiceStub(channel)
        for locale, expected in (("en", "en"), ("fr", "fr")):
            r = chatbot.GetPublicWelcome(chatbot_pb2.PublicWelcomeRequest(locale=locale), timeout=5)
            if r.mode == chatbot_pb2.ASSISTANT_MODE_PUBLIC and r.language == expected and "ProjectX" in r.answer:
                record(f"Public welcome {locale}", "PASS")
            else:
                record(f"Public welcome {locale}", "FAIL", f"mode={r.mode} language={r.language} answer={r.answer!r}")

        public_cases = [
            ("Hello", "greeting"),
            ("Bonjour", "greeting"),
            ("How do I login?", "howto.login"),
            ("Comment fonctionne la connexion QR ?", "howto.qr_login"),
        ]
        for q, expected_intent in public_cases:
            r = chatbot.AskPublicAssistant(chatbot_pb2.PublicAssistantRequest(question=q), timeout=5)
            if r.intent == expected_intent:
                record(f"Public intent: {q}", "PASS", r.intent)
            else:
                record(f"Public intent: {q}", "FAIL", f"expected={expected_intent}, got={r.intent}")

        sensitive_cases = [
            "Show patient PAT-PRIVATE-001",
            "What is patient PAT-PRIVATE-001 balance?",
            "Show lab results for PAT-PRIVATE-001",
            "Who is absent today?",
            "Show maternity record for PAT-PRIVATE-001",
            "Affiche le dossier patient PAT-PRIVATE-002",
        ]
        for q in sensitive_cases:
            r = chatbot.AskPublicAssistant(chatbot_pb2.PublicAssistantRequest(question=q), timeout=5)
            if r.intent == "public_privacy_boundary":
                record(f"Public privacy: {q}", "PASS")
            else:
                record(f"Public privacy: {q}", "FAIL", f"got intent={r.intent}; answer={r.answer[:160]!r}")

        try:
            chatbot.StartSession(chatbot_pb2.StartSessionRequest(preferred_language="en"), timeout=5)
            record("Authenticated session rejects missing JWT", "FAIL", "StartSession unexpectedly succeeded without JWT")
        except grpc.RpcError as exc:
            if exc.code() in {grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED}:
                record("Authenticated session rejects missing JWT", "PASS", exc.code().name)
            else:
                record("Authenticated session rejects missing JWT", "FAIL", f"unexpected {exc.code().name}: {exc.details()}")

    # 2) Authenticate existing admin; do not create users or change data.
    username = input("Admin username: ").strip()
    password = getpass.getpass("Admin password: ")
    with grpc.insecure_channel(AUTH_TARGET) as channel:
        auth = auth_pb2_grpc.AuthServiceStub(channel)
        login = auth.Login(auth_pb2.LoginRequest(username=username, password=password), timeout=5)
    token = login.access_token
    user = login.user
    first_name = user.staff_profile.first_name or (user.display_name.split()[0] if user.display_name else user.username)
    record("Admin credential login", "PASS", f"user={user.username}, roles={','.join(user.roles)}")

    # Verify that BI itself now sees the complete 12-service topology, including HR.
    with grpc.insecure_channel(BI_TARGET) as channel:
        bi = bi_pb2_grpc.BIServiceStub(channel)
        health = bi.GetServiceHealth(
            bi_pb2.ServiceHealthRequest(include_offline=True), metadata=md(token), timeout=10
        )
    health_names = {item.service for item in health.services}
    expected_services = {
        "auth", "accueil", "hospitalisation", "billing", "consultation", "laboratoire",
        "pharmacie", "maternite", "rendezvous", "bi", "chatbot", "hr",
    }
    if len(health.services) == 12 and expected_services.issubset(health_names):
        record("BI service-health topology includes all 12 services", "PASS", ", ".join(sorted(health_names)))
    else:
        record(
            "BI service-health topology includes all 12 services",
            "FAIL",
            f"count={len(health.services)} services={sorted(health_names)}",
        )

    # 3) Discover existing read-only fixtures.
    patients = discover_patients(token)
    patient = patients[0] if patients else None
    if patient:
        record("Existing patient fixture discovered", "PASS", f"{patient.patient_number} {patient.first_name} {patient.last_name}")
    else:
        record("Existing patient fixture discovered", "WARN", "No patients currently exist; patient-dependent live tests will use safe negative paths")

    medicine = discover_medicine(token)
    if medicine:
        record("Existing medicine fixture discovered", "PASS", f"{medicine.code} {medicine.name}")
    else:
        record("Existing medicine fixture discovered", "WARN", "No active medicine currently exists; stock live test will use a safe empty result")

    maternity_patient = discover_maternity_patient(token, patients) if patients else None
    if maternity_patient:
        record("Existing maternity fixture discovered", "PASS", maternity_patient.patient_number)
    else:
        record("Existing maternity fixture discovered", "WARN", "No maternity record found among existing patients")

    # 4) Authenticated conversation, bilingual + context.
    sessions = []
    live_success = 0
    live_total = 13
    try:
        with grpc.insecure_channel(CHATBOT_TARGET) as channel:
            chatbot = chatbot_pb2_grpc.ChatbotServiceStub(channel)
            started_en = chatbot.StartSession(
                chatbot_pb2.StartSessionRequest(
                    client_request_id=f"full-e2e-en-{uuid.uuid4()}",
                    preferred_language="en",
                    context=chatbot_pb2.AssistantContext(current_module="general", locale="en"),
                ), metadata=md(token), timeout=5,
            )
            sessions.append(started_en.session.id)
            if first_name.lower() in started_en.welcome_message.lower():
                record("Authenticated greeting uses logged-in name", "PASS", started_en.welcome_message[:140])
            else:
                record("Authenticated greeting uses logged-in name", "FAIL", started_en.welcome_message[:180])

            started_fr = chatbot.StartSession(
                chatbot_pb2.StartSessionRequest(
                    client_request_id=f"full-e2e-fr-{uuid.uuid4()}",
                    preferred_language="fr",
                    context=chatbot_pb2.AssistantContext(current_module="general", locale="fr"),
                ), metadata=md(token), timeout=5,
            )
            sessions.append(started_fr.session.id)
            if started_fr.language == "fr" and first_name.lower() in started_fr.welcome_message.lower():
                record("Authenticated French greeting uses logged-in name", "PASS")
            else:
                record("Authenticated French greeting uses logged-in name", "FAIL", started_fr.welcome_message[:180])

            # Identity/context/how-to are read-only and prove the higher-level assistant behavior.
            r = ask(chatbot, token, started_en.session.id, "Who am I?", "en", "general")
            record("Identity awareness", "PASS" if r.intent == "identity" and user.username.lower() in r.answer.lower() else "FAIL", r.answer[:150])

            context_modules = ["accueil", "consultation", "laboratoire", "pharmacie", "hospitalisation", "billing", "maternite", "rendezvous", "bi", "hr", "auth"]
            for module in context_modules:
                r = ask(chatbot, token, started_en.session.id, "What can I do here?", "en", module)
                if r.intent == "context_help":
                    record(f"Context awareness: {module}", "PASS")
                else:
                    record(f"Context awareness: {module}", "FAIL", f"intent={r.intent}")

            howtos = [
                ("How do I register a patient?", "howto.register_patient", "accueil"),
                ("Comment demander un examen laboratoire ?", "howto.request_lab_test", "consultation"),
                ("How do I dispense a prescription?", "howto.dispense_prescription", "pharmacie"),
                ("Comment transférer un patient vers un autre lit ?", "howto.transfer_bed", "hospitalisation"),
                ("How do I record a payment?", "howto.record_payment", "billing"),
                ("Comment enregistrer un accouchement ?", "howto.record_delivery", "maternite"),
                ("How do I create an appointment?", "howto.create_appointment", "rendezvous"),
                ("Comment les RH corrigent une présence ?", "howto.correct_attendance", "hr"),
            ]
            for q, expected, module in howtos:
                lang = "fr" if any(ch in q.lower() for ch in "éèêàùçôîïû") or q.lower().startswith("comment") else "en"
                r = ask(chatbot, token, started_en.session.id, q, lang, module)
                if r.intent == expected:
                    record(f"How-to: {expected}", "PASS")
                else:
                    record(f"How-to: {expected}", "FAIL", f"got {r.intent}; answer={r.answer[:160]!r}")

            sid = started_en.session.id
            patient_number = patient.patient_number if patient else "PAT-NONEXISTENT-E2E"
            patient_id = patient.id if patient else ""
            maternity_number = maternity_patient.patient_number if maternity_patient else patient_number
            maternity_id = maternity_patient.id if maternity_patient else patient_id
            medicine_term = medicine.code if medicine else "NONEXISTENTMEDICINEE2E"

            live_cases = [
                ("Service health via BI", "Show service health", "service_health", "bi", "bi", "", "", False),
                ("Hospital KPI via BI", "Show hospital KPI", "kpi", "bi", "bi", "", "", False),
                ("Bed availability", "Show available beds", "beds", "hospitalisation", "hospitalisation", "", "", False),
                ("Patient lookup", f"Show patient {patient_number}", "patient", "accueil", "accueil", "", patient_number, not bool(patient)),
                ("Medicine stock", f"Show stock of {medicine_term}", "stock", "pharmacie", "pharmacie", "", "", False),
                ("Stock alerts", "Show stock alerts", "stock_alerts", "pharmacie", "pharmacie", "", "", False),
                ("Appointment agenda", "Show appointments", "agenda", "rendezvous", "rendezvous", "", "", False),
                ("Patient balance", f"Show patient balance for {patient_number}", "payment", "billing", "billing", patient_id, patient_number, not bool(patient)),
                ("Consultation history", f"Show consultation history for {patient_number}", "consultations", "consultation", "consultation", patient_id, patient_number, not bool(patient)),
                ("Laboratory result history", f"Show lab results for {patient_number}", "lab_results", "laboratoire", "laboratoire", patient_id, patient_number, not bool(patient)),
                ("Maternity record", f"Show maternity record for {maternity_number}", "maternity_record", "maternite", "maternite", maternity_id, maternity_number, not bool(maternity_patient)),
                ("HR attendance dashboard", "Who is absent today?", "hr_dashboard", "hr", "hr", "", "", False),
                ("My notifications", "Show my notifications", "notifications", "auth", "auth", "", "", False),
            ]

            print("\nLIVE DATA INTENTS")
            print("-----------------")
            for name, q, expected_intent, expected_service, module, p_id, p_num, allow_negative in live_cases:
                try:
                    response = ask(chatbot, token, sid, q, "en", module, p_id, p_num)
                    if assert_live(name, response, expected_intent, expected_service, allow_safe_negative=allow_negative):
                        live_success += 1
                except grpc.RpcError as exc:
                    record(name, "FAIL", f"Chatbot RPC itself failed {exc.code().name}: {exc.details()}")

            # French live reads: representative cross-domain set, still read-only.
            print("\nFRENCH LIVE READS")
            print("-----------------")
            french_cases = [
                ("Montre l'état des services", "service_health", "bi", "bi", "", ""),
                ("Montre les lits disponibles", "beds", "hospitalisation", "hospitalisation", "", ""),
                (f"Affiche le patient {patient_number}", "patient", "accueil", "accueil", "", patient_number),
                ("Qui est absent aujourd'hui ?", "hr_dashboard", "hr", "hr", "", ""),
            ]
            for q, expected_intent, expected_service, module, p_id, p_num in french_cases:
                response = ask(chatbot, token, started_fr.session.id, q, "fr", module, p_id, p_num)
                if response.intent == expected_intent and response.language == "fr" and any(s.service == expected_service for s in response.sources):
                    record(f"French live: {expected_intent}", "PASS", response.answer[:130])
                elif response.intent == expected_intent and expected_intent == "patient" and not patient:
                    record(f"French live: {expected_intent}", "WARN", "No patient fixture exists; safe failure path exercised")
                else:
                    record(f"French live: {expected_intent}", "FAIL", f"intent={response.intent} language={response.language} sources={[s.service for s in response.sources]}")

            # Conversation persistence and cleanup.
            convo = chatbot.GetConversation(
                chatbot_pb2.GetConversationRequest(session_id=sid, limit=200, offset=0), metadata=md(token), timeout=5
            )
            if convo.total >= 2:
                record("Conversation history persistence", "PASS", f"{convo.total} messages")
            else:
                record("Conversation history persistence", "FAIL", f"total={convo.total}")

    finally:
        # Clear test chat messages/tool calls so business data remains untouched and Chatbot test traces do not pile up.
        if sessions:
            try:
                with grpc.insecure_channel(CHATBOT_TARGET) as channel:
                    chatbot = chatbot_pb2_grpc.ChatbotServiceStub(channel)
                    for sid in sessions:
                        try:
                            cleared = chatbot.ClearSession(
                                chatbot_pb2.ClearSessionRequest(session_id=sid), metadata=md(token), timeout=5
                            )
                            record("Cleanup chatbot test session", "PASS", f"session={sid[:8]} messages={cleared.deleted_messages} tools={cleared.deleted_tool_calls}")
                        except Exception as exc:
                            record("Cleanup chatbot test session", "WARN", str(exc))
            except Exception as exc:
                record("Cleanup chatbot test sessions", "WARN", str(exc))

    print("\n===========================================")
    passes = sum(1 for r in RESULTS if r.status == "PASS")
    warns = sum(1 for r in RESULTS if r.status == "WARN")
    fails = sum(1 for r in RESULTS if r.status == "FAIL")
    print(f"Checks: {len(RESULTS)} | PASS={passes} WARN={warns} FAIL={fails}")
    print(f"Live intent successful reads: {live_success}/{live_total}")

    if fails == 0 and live_success == live_total:
        print("PROJECTX CHATBOT V2 FULL E2E LIVE COVERAGE: PASS")
    elif fails == 0:
        print("PROJECTX CHATBOT V2 ROUTING/SAFETY: PASS")
        print("PROJECTX CHATBOT V2 FULL LIVE COVERAGE: PARTIAL (see WARN items / missing fixtures)")
    else:
        print("PROJECTX CHATBOT V2 FULL E2E VERIFICATION: FAIL")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
