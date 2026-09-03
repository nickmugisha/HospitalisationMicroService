from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import delete, func, select, text

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from bi.v1 import bi_pb2, bi_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc
from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc
from common.v1 import common_pb2
from consultation.v1 import consultation_pb2, consultation_pb2_grpc
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from hr.v1 import hr_pb2, hr_pb2_grpc
from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc
from maternite.v1 import maternite_pb2, maternite_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc

from database.chatbot_session import ChatbotSessionLocal, engine
from services.chatbot.assistant_engine import (
    PROCEDURES,
    build_suggestions,
    context_help,
    detect_language,
    extract_patient_number,
    friendly_name,
    generic_help,
    goodbye_response,
    greeting,
    identify_live_intent,
    is_context_help,
    is_goodbye,
    is_greeting,
    is_identity_question,
    is_thanks,
    likely_sensitive_public_question,
    looks_like_howto,
    match_procedure,
    normalize_module,
    public_privacy_response,
    render_procedure,
    thanks_response,
)
from services.chatbot.config import (
    ACCUEIL_GRPC_TARGET,
    AUTH_GRPC_TARGET,
    BILLING_GRPC_TARGET,
    BI_GRPC_TARGET,
    CONSULTATION_GRPC_TARGET,
    HOSPITALISATION_GRPC_TARGET,
    HR_GRPC_TARGET,
    LABORATOIRE_GRPC_TARGET,
    MATERNITE_GRPC_TARGET,
    PHARMACIE_GRPC_TARGET,
    RENDEZVOUS_GRPC_TARGET,
    SERVICE_VERSION,
)
from services.chatbot.models import ChatMessage, ChatSession, ToolCall
from services.common.health_compat import build_health_response_compat

logger = logging.getLogger("projectx.chatbot.service")

PUBLIC_RATE_LIMIT = 30
PUBLIC_RATE_WINDOW_SECONDS = 60
_PUBLIC_LOCK = threading.Lock()
_PUBLIC_HITS: dict[str, list[float]] = {}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ts(value=None):
    out = Timestamp()
    value = value or now_utc()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    out.FromDatetime(value.astimezone(timezone.utc))
    return out


def build_health(status, message):
    return build_health_response_compat("chatbot", status, message, SERVICE_VERSION)


def _metadata_token(context) -> str:
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization" and item.value.strip():
            value = item.value.strip()
            if value.lower().startswith("bearer "):
                return value[7:].strip()
    return ""


def auth_user(context):
    token = _metadata_token(context)
    if not token:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing Bearer authorization metadata.")
    try:
        with grpc.insecure_channel(AUTH_GRPC_TARGET) as channel:
            response = auth_pb2_grpc.AuthServiceStub(channel).ValidateToken(
                auth_pb2.ValidateTokenRequest(access_token=token), timeout=3
            )
    except grpc.RpcError as exc:
        context.abort(grpc.StatusCode.UNAVAILABLE, f"Authentication service unavailable: {exc.code().name}")
    if not response.valid:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or expired access token.")
    if "chatbot.ask" not in set(response.user.permissions):
        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Missing permission: chatbot.ask")
    return response.user, token


def md(token):
    return (("authorization", f"Bearer {token}"),)


def session_proto(session):
    return chatbot_pb2.ChatSession(
        id=session.id,
        user_id=session.user_id,
        started_at=ts(session.started_at),
        updated_at=ts(session.updated_at),
    )


def message_proto(message):
    role = chatbot_pb2.MESSAGE_ROLE_USER if message.role == "USER" else chatbot_pb2.MESSAGE_ROLE_ASSISTANT
    return chatbot_pb2.ChatMessage(
        id=message.id,
        session_id=message.session_id,
        role=role,
        content=message.content,
        created_at=ts(message.created_at),
    )


def source(service, rpc, correlation_id, success, message):
    return chatbot_pb2.Source(
        service=service,
        rpc=rpc,
        correlation_id=correlation_id,
        success=success,
        message=message,
        checked_at=ts(),
    )


def _public_rate_limit(context):
    peer = context.peer() or "unknown"
    now = time.monotonic()
    with _PUBLIC_LOCK:
        hits = [stamp for stamp in _PUBLIC_HITS.get(peer, []) if now - stamp < PUBLIC_RATE_WINDOW_SECONDS]
        if len(hits) >= PUBLIC_RATE_LIMIT:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Public assistant rate limit exceeded. Please retry shortly.")
        hits.append(now)
        _PUBLIC_HITS[peer] = hits


def _context_module(request_context) -> str:
    if request_context is None:
        return "general"
    return normalize_module(getattr(request_context, "current_module", "") or getattr(request_context, "current_route", ""))


def _context_locale(request_context) -> str:
    return getattr(request_context, "locale", "") if request_context is not None else ""


def _recent_text(db, session_id: str, limit: int = 8) -> str:
    rows = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()
    )
    return "\n".join(item.content for item in rows)


def _resolve_patient_id(question: str, request_context, prior_text: str, user, token: str):
    active_patient_id = getattr(request_context, "active_patient_id", "").strip() if request_context is not None else ""
    if active_patient_id:
        return active_patient_id, getattr(request_context, "active_patient_number", "").strip(), []

    patient_number = extract_patient_number(
        question,
        getattr(request_context, "active_patient_number", "") if request_context is not None else "",
        prior_text,
    )
    if not patient_number:
        return "", "", []
    if "accueil.patient.read" not in set(user.permissions):
        return "", patient_number, []
    with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as channel:
        patient = accueil_pb2_grpc.AccueilServiceStub(channel).GetPatient(
            accueil_pb2.GetPatientRequest(patient_number=patient_number), metadata=md(token), timeout=3
        ).patient
    return patient.id, patient.patient_number, [source("accueil", "GetPatient", "", True, "Patient identity resolved by Accueil.")]


def _money_text(money) -> str:
    currency = "BIF"
    descriptor = getattr(money, "DESCRIPTOR", None)
    if descriptor is not None:
        fields = descriptor.fields_by_name
        if "currency_code" in fields:
            currency = money.currency_code or "BIF"
        elif "currency" in fields:
            currency = money.currency or "BIF"
    return f"{money.amount_minor} {currency}"


def _grpc_error_message(language: str, service_name: str, exc: grpc.RpcError) -> str:
    if language == "fr":
        return f"Je n'ai pas pu terminer la demande car le service {service_name} a répondu {exc.code().name}. Je n'invente aucun résultat."
    return f"I could not complete the request because {service_name} returned {exc.code().name}. I will not invent a result."


class ChatbotService(chatbot_pb2_grpc.ChatbotServiceServicer):
    def _get_session(self, db, session_id, user_id, context):
        row = db.get(ChatSession, session_id)
        if row is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Chat session not found.")
        if row.user_id != user_id:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "This session belongs to another user.")
        return row

    def _record_tool(self, db, session_id, message_id, service_name, rpc, correlation_id, outcome, detail):
        db.add(
            ToolCall(
                session_id=session_id,
                message_id=message_id,
                service=service_name,
                rpc=rpc,
                correlation_id=correlation_id,
                outcome=outcome,
                detail=detail,
            )
        )

    # ---------------- PUBLIC / LOGIN PAGE ----------------
    def GetPublicWelcome(self, request, context):
        _public_rate_limit(context)
        language = detect_language(locale=request.locale)
        correlation_id = str(uuid.uuid4())
        return chatbot_pb2.PublicAssistantResponse(
            answer=greeting(language),
            intent="greeting",
            confidence=1.0,
            language=language,
            suggested_questions=build_suggestions(language, (), "login", public=True),
            mode=chatbot_pb2.ASSISTANT_MODE_PUBLIC,
            correlation_id=correlation_id,
        )

    def AskPublicAssistant(self, request, context):
        _public_rate_limit(context)
        question = request.question.strip()
        if not question:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Question is required.")
        if len(question) > 1000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Question is too long.")
        language = detect_language(question, request.locale)
        correlation_id = request.correlation_id.strip() or str(uuid.uuid4())
        intent = "public_help"
        confidence = 0.70

        if is_greeting(question):
            answer = greeting(language)
            intent, confidence = "greeting", 1.0
        elif is_thanks(question):
            answer = thanks_response(language)
            intent, confidence = "thanks", 0.99
        elif is_goodbye(question):
            answer = goodbye_response(language)
            intent, confidence = "goodbye", 0.99
        else:
            procedure = match_procedure(question)
            live_intent = identify_live_intent(question)

            # On the unauthenticated login page, a clear HOW-TO question may receive
            # generic procedural guidance, but any live/sensitive-data lookup is
            # blocked before generic procedure matching. This prevents requests such
            # as "Show patient PAT-..." from being mistaken for a how-to procedure.
            if procedure is not None and looks_like_howto(question):
                answer, _ = render_procedure(procedure, language, public=True)
                intent, confidence = f"howto.{procedure.key}", 0.92
            elif likely_sensitive_public_question(question) or live_intent is not None:
                answer = public_privacy_response(language)
                intent, confidence = "public_privacy_boundary", 0.99
            elif procedure is not None:
                answer, _ = render_procedure(procedure, language, public=True)
                intent, confidence = f"howto.{procedure.key}", 0.88
            else:
                if language == "fr":
                    answer = (
                        "Je peux vous aider sur la page de connexion: connexion par identifiant, connexion QR, compte en attente et fonctionnement général de ProjectX. "
                        "Pour toute donnée patient, clinique, RH ou financière, vous devez d'abord vous authentifier."
                    )
                else:
                    answer = (
                        "I can help on the login page with credential login, QR login, pending-account questions and general ProjectX guidance. "
                        "For patient, clinical, HR or financial data, you must sign in first."
                    )

        logger.info("rpc=AskPublicAssistant peer=%s intent=%s correlation_id=%s outcome=OK", context.peer(), intent, correlation_id)
        return chatbot_pb2.PublicAssistantResponse(
            answer=answer,
            intent=intent,
            confidence=confidence,
            language=language,
            suggested_questions=build_suggestions(language, (), "login", public=True),
            mode=chatbot_pb2.ASSISTANT_MODE_PUBLIC,
            correlation_id=correlation_id,
        )

    # ---------------- AUTHENTICATED ----------------
    def StartSession(self, request, context):
        user, _ = auth_user(context)
        language = detect_language(locale=request.preferred_language or _context_locale(request.context))
        module = _context_module(request.context)
        db = ChatbotSessionLocal()
        try:
            key = request.client_request_id.strip()
            if key:
                existing = db.scalar(select(ChatSession).where(ChatSession.client_request_id == key))
                if existing:
                    if existing.user_id != user.id:
                        context.abort(grpc.StatusCode.ALREADY_EXISTS, "client_request_id already belongs to another user.")
                    return chatbot_pb2.SessionResponse(
                        session=session_proto(existing),
                        welcome_message=greeting(language, friendly_name(user)),
                        language=language,
                        suggested_questions=build_suggestions(language, user.permissions, module),
                        mode=chatbot_pb2.ASSISTANT_MODE_AUTHENTICATED,
                    )
            row = ChatSession(user_id=user.id, client_request_id=key or None)
            db.add(row)
            db.commit()
            db.refresh(row)
            return chatbot_pb2.SessionResponse(
                session=session_proto(row),
                welcome_message=greeting(language, friendly_name(user)),
                language=language,
                suggested_questions=build_suggestions(language, user.permissions, module),
                mode=chatbot_pb2.ASSISTANT_MODE_AUTHENTICATED,
            )
        finally:
            db.close()

    def GetCapabilities(self, request, context):
        user, _ = auth_user(context)
        language = detect_language(locale=request.language or _context_locale(request.context))
        permissions = set(user.permissions)
        module = _context_module(request.context)
        out = []

        for procedure in PROCEDURES:
            if module != "general" and procedure.module != module:
                continue
            if procedure.permission and procedure.permission not in permissions:
                continue
            out.append(
                chatbot_pb2.Capability(
                    intent=f"howto.{procedure.key}",
                    description=procedure.title_fr if language == "fr" else procedure.title_en,
                    required_permission=procedure.permission,
                    examples=[
                        f"Comment {procedure.title_fr[0].lower() + procedure.title_fr[1:]} ?"
                        if language == "fr"
                        else f"How do I {procedure.title_en[0].lower() + procedure.title_en[1:]}?"
                    ],
                    module=procedure.module,
                )
            )

        live_caps = [
            ("patient", "accueil.patient.read", "accueil", "Search patient data", "Rechercher des données patient"),
            ("beds", "hospitalisation.read", "hospitalisation", "Read bed availability", "Consulter la disponibilité des lits"),
            ("stock", "pharmacy.stock.read", "pharmacie", "Read medicine stock", "Consulter le stock médicament"),
            ("stock_alerts", "pharmacy.stock.read", "pharmacie", "Read stock alerts", "Consulter les alertes de stock"),
            ("agenda", "appointment.read", "rendezvous", "Read appointment agenda", "Consulter l'agenda des rendez-vous"),
            ("payment", "billing.read", "billing", "Read patient balance", "Consulter le solde patient"),
            ("consultations", "consultation.read", "consultation", "Read consultation history", "Consulter l'historique des consultations"),
            ("lab_results", "lab.orders.read", "laboratoire", "Read laboratory-result history", "Consulter l'historique des résultats laboratoire"),
            ("maternity_record", "maternity.read", "maternite", "Read maternity record", "Consulter le dossier maternité"),
            ("hr_dashboard", "hr.dashboard.read", "hr", "Read HR attendance dashboard", "Consulter le tableau de bord RH/présences"),
            ("notifications", "notification.read", "auth", "Read my notifications", "Consulter mes notifications"),
            ("kpi", "bi.dashboard.read", "bi", "Read hospital KPI", "Consulter les KPI hospitaliers"),
            ("service_health", "bi.dashboard.read", "bi", "Read service health", "Consulter l'état des services"),
        ]
        for intent, permission, cap_module, en, fr in live_caps:
            if permission in permissions and (module == "general" or module == cap_module):
                out.append(
                    chatbot_pb2.Capability(
                        intent=intent,
                        description=fr if language == "fr" else en,
                        required_permission=permission,
                        examples=[],
                        module=cap_module,
                    )
                )
        return chatbot_pb2.GetCapabilitiesResponse(capabilities=out)

    def AskAssistant(self, request, context):
        user, token = auth_user(context)
        question = request.question.strip()
        if not question:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Question is required.")
        if len(question) > 2000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Question is too long.")

        correlation_id = request.correlation_id.strip() or str(uuid.uuid4())
        language = detect_language(question, _context_locale(request.context))
        module = _context_module(request.context)
        permissions = set(user.permissions)
        name = friendly_name(user)
        db = ChatbotSessionLocal()
        try:
            session = self._get_session(db, request.session_id.strip(), user.id, context)
            prior_text = _recent_text(db, session.id)
            user_message = ChatMessage(session_id=session.id, role="USER", content=question)
            db.add(user_message)
            db.flush()

            answer = ""
            intent = "help"
            confidence = 0.65
            permission_note = ""
            sources = []

            # Conversational layer first.
            if is_greeting(question):
                answer = greeting(language, name)
                intent, confidence = "greeting", 1.0
            elif is_thanks(question):
                answer = thanks_response(language, name)
                intent, confidence = "thanks", 0.99
            elif is_goodbye(question):
                answer = goodbye_response(language, name)
                intent, confidence = "goodbye", 0.99
            elif is_identity_question(question):
                roles = ", ".join(user.roles) if user.roles else ("aucun rôle" if language == "fr" else "no role")
                if language == "fr":
                    answer = f"Vous êtes {user.display_name or user.username}. Rôle(s) vérifié(s) par Auth: {roles}."
                else:
                    answer = f"You are {user.display_name or user.username}. Role(s) verified by Auth: {roles}."
                intent, confidence = "identity", 0.99
            elif is_context_help(question):
                answer = context_help(module, permissions, language)
                intent, confidence = "context_help", 0.97
            else:
                procedure = match_procedure(question)
                # Explicit how-to questions always use the procedural knowledge layer.
                # Direct write-like phrases are also guided rather than silently executed.
                write_guidance = procedure is not None and procedure.key not in {"login", "qr_login", "search_patient", "view_kpi"}
                if procedure is not None and (looks_like_howto(question) or write_guidance):
                    answer, permission_note = render_procedure(procedure, language, permissions, public=False)
                    intent, confidence = f"howto.{procedure.key}", 0.96 if looks_like_howto(question) else 0.88
                    if not looks_like_howto(question) and language == "fr":
                        answer = "Je peux vous guider pour cette opération. Les écritures sensibles ne sont pas exécutées automatiquement par le chatbot v2.\n\n" + answer
                    elif not looks_like_howto(question):
                        answer = "I can guide you through this operation. Chatbot v2 does not automatically execute sensitive writes.\n\n" + answer
                else:
                    live = identify_live_intent(question)
                    if live is None:
                        answer = generic_help(language, permissions, module)
                        intent, confidence = "help", 0.65
                    else:
                        intent, confidence, required_permission = live
                        if required_permission not in permissions:
                            permission_note = (
                                f"Votre compte ne possède pas la permission `{required_permission}` requise pour cette information."
                                if language == "fr"
                                else f"Your current account does not have the `{required_permission}` permission required for this information."
                            )
                            answer = permission_note
                            confidence = 0.99
                        else:
                            try:
                                # LIVE READS: all downstream services still validate the same bearer token.
                                if intent == "service_health":
                                    with grpc.insecure_channel(BI_GRPC_TARGET) as channel:
                                        result = bi_pb2_grpc.BIServiceStub(channel).GetServiceHealth(
                                            bi_pb2.ServiceHealthRequest(include_offline=True), metadata=md(token), timeout=10
                                        )
                                    online = [x.service for x in result.services if x.status == bi_pb2.SERVICE_STATUS_ONLINE]
                                    degraded = [x.service for x in result.services if x.status == bi_pb2.SERVICE_STATUS_DEGRADED]
                                    offline = [x.service for x in result.services if x.status == bi_pb2.SERVICE_STATUS_OFFLINE]
                                    if language == "fr":
                                        answer = f"Services en ligne: {len(online)}. Dégradés: {', '.join(degraded) if degraded else 'aucun'}. Hors ligne: {', '.join(offline) if offline else 'aucun'}."
                                    else:
                                        answer = f"Services online: {len(online)}. Degraded: {', '.join(degraded) if degraded else 'none'}. Offline: {', '.join(offline) if offline else 'none'}."
                                    sources.append(source("bi", "GetServiceHealth", correlation_id, True, "Service health obtained from BI."))
                                    self._record_tool(db, session.id, user_message.id, "bi", "GetServiceHealth", correlation_id, "OK", answer)

                                elif intent == "kpi":
                                    with grpc.insecure_channel(BI_GRPC_TARGET) as channel:
                                        result = bi_pb2_grpc.BIServiceStub(channel).GetDashboard(
                                            bi_pb2.DashboardRequest(), metadata=md(token), timeout=10
                                        )
                                    wanted = {
                                        "patients.total", "consultations.total", "admissions.active", "revenue.paid",
                                        "revenue.balance", "beds.available", "stock.units", "appointments.total",
                                    }
                                    values = [f"{m.label}: {m.value} {m.unit}".strip() for m in result.metrics if m.code in wanted]
                                    quality = bi_pb2.DataQuality.Name(result.quality)
                                    prefix = "KPI hôpital" if language == "fr" else "Hospital KPI"
                                    answer = f"{prefix} ({quality}): " + ("; ".join(values) if values else ("Aucune valeur disponible." if language == "fr" else "No KPI values available."))
                                    if result.warnings:
                                        answer += (" Avertissements: " if language == "fr" else " Warnings: ") + " | ".join(list(result.warnings)[:3])
                                    sources.append(source("bi", "GetDashboard", correlation_id, True, f"Dashboard quality: {quality}."))
                                    self._record_tool(db, session.id, user_message.id, "bi", "GetDashboard", correlation_id, "OK", quality)

                                elif intent == "beds":
                                    with grpc.insecure_channel(HOSPITALISATION_GRPC_TARGET) as channel:
                                        result = hospitalisation_pb2_grpc.HospitalisationServiceStub(channel).GetBedAvailability(
                                            hospitalisation_pb2.GetBedAvailabilityRequest(available_only=True), metadata=md(token), timeout=3
                                        )
                                    if language == "fr":
                                        answer = f"Lits: {result.available} disponibles, {result.occupied} occupés, {result.out_of_service} hors service, {result.total} au total."
                                    else:
                                        answer = f"Beds: {result.available} available, {result.occupied} occupied, {result.out_of_service} out of service, {result.total} total."
                                    sources.append(source("hospitalisation", "GetBedAvailability", correlation_id, True, "Bed availability obtained."))
                                    self._record_tool(db, session.id, user_message.id, "hospitalisation", "GetBedAvailability", correlation_id, "OK", answer)

                                elif intent == "patient":
                                    patient_number = extract_patient_number(
                                        question,
                                        getattr(request.context, "active_patient_number", ""),
                                        prior_text,
                                    )
                                    with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as channel:
                                        stub = accueil_pb2_grpc.AccueilServiceStub(channel)
                                        if patient_number:
                                            result = stub.GetPatient(
                                                accueil_pb2.GetPatientRequest(patient_number=patient_number), metadata=md(token), timeout=3
                                            )
                                            patient = result.patient
                                            answer = (
                                                f"Patient {patient.patient_number}: {patient.first_name} {patient.last_name}, téléphone {patient.phone or 'non renseigné'}."
                                                if language == "fr"
                                                else f"Patient {patient.patient_number}: {patient.first_name} {patient.last_name}, phone {patient.phone or 'not provided'}."
                                            )
                                            rpc = "GetPatient"
                                        else:
                                            cleaned = re.sub(r"(?i)patient|find|search|show|chercher|rechercher|trouver|afficher", " ", question).strip()
                                            result = stub.SearchPatients(
                                                accueil_pb2.SearchPatientsRequest(query=cleaned, limit=5, offset=0), metadata=md(token), timeout=3
                                            )
                                            listing = ", ".join(f"{p.patient_number} {p.first_name} {p.last_name}" for p in result.patients[:5])
                                            answer = (f"{result.total} patient(s) trouvé(s). {listing}" if language == "fr" else f"{result.total} patient(s) found. {listing}")
                                            rpc = "SearchPatients"
                                    sources.append(source("accueil", rpc, correlation_id, True, "Patient data obtained from Accueil."))
                                    self._record_tool(db, session.id, user_message.id, "accueil", rpc, correlation_id, "OK", answer)

                                elif intent == "stock":
                                    cleaned = re.sub(r"(?i)stock|medicine|medication|medicament|médicament|pharmacy|pharmacie|of|de|du|des", " ", question).strip()
                                    with grpc.insecure_channel(PHARMACIE_GRPC_TARGET) as channel:
                                        stub = pharmacie_pb2_grpc.PharmacieServiceStub(channel)
                                        result = stub.SearchMedicines(
                                            pharmacie_pb2.SearchMedicinesRequest(query=cleaned, active_only=True, limit=5, offset=0), metadata=md(token), timeout=3
                                        )
                                        if not result.medicines:
                                            answer = "Aucun médicament actif ne correspond à la demande." if language == "fr" else "No active medicine matched the request."
                                        else:
                                            medicine = result.medicines[0]
                                            stock = stub.GetStock(
                                                pharmacie_pb2.GetStockRequest(medicine_ref=medicine.code), metadata=md(token), timeout=3
                                            ).stock
                                            if language == "fr":
                                                answer = f"{medicine.name} {medicine.strength}: {stock.total_available} {medicine.unit}(s) disponibles dans {len(stock.batches)} lot(s)."
                                            else:
                                                answer = f"{medicine.name} {medicine.strength}: {stock.total_available} {medicine.unit}(s) available across {len(stock.batches)} batch(es)."
                                    sources.append(source("pharmacie", "SearchMedicines/GetStock", correlation_id, True, "Stock obtained from Pharmacie."))
                                    self._record_tool(db, session.id, user_message.id, "pharmacie", "SearchMedicines/GetStock", correlation_id, "OK", answer)

                                elif intent == "stock_alerts":
                                    with grpc.insecure_channel(PHARMACIE_GRPC_TARGET) as channel:
                                        result = pharmacie_pb2_grpc.PharmacieServiceStub(channel).ListStockAlerts(
                                            pharmacie_pb2.ListStockAlertsRequest(days_to_expiry=30), metadata=md(token), timeout=3
                                        )
                                    top = list(result.alerts[:5])
                                    details = "; ".join(f"{x.medicine_name}: {x.message}" for x in top)
                                    if language == "fr":
                                        answer = f"{result.total} alerte(s) de stock. " + (details if details else "Aucune alerte détaillée à afficher.")
                                    else:
                                        answer = f"{result.total} stock alert(s). " + (details if details else "No alert details to display.")
                                    sources.append(source("pharmacie", "ListStockAlerts", correlation_id, True, "Stock alerts obtained."))
                                    self._record_tool(db, session.id, user_message.id, "pharmacie", "ListStockAlerts", correlation_id, "OK", answer)

                                elif intent == "agenda":
                                    start = Timestamp(); start.FromDatetime(now_utc())
                                    end = Timestamp(); end.FromDatetime(now_utc() + timedelta(days=7))
                                    provider = ""
                                    match = re.search(r"DOC-[A-Z0-9_-]+", question, re.I)
                                    if match:
                                        provider = match.group(0).upper()
                                    with grpc.insecure_channel(RENDEZVOUS_GRPC_TARGET) as channel:
                                        result = rendezvous_pb2_grpc.RendezvousServiceStub(channel).ListAgenda(
                                            rendezvous_pb2.ListAgendaRequest(provider_id=provider, from_at=start, to_at=end, limit=20, offset=0),
                                            metadata=md(token), timeout=3,
                                        )
                                    if language == "fr":
                                        answer = f"{result.total} rendez-vous dans les 7 prochains jours" + (f" pour {provider}" if provider else "") + "."
                                    else:
                                        answer = f"{result.total} appointment(s) in the next 7 days" + (f" for {provider}" if provider else "") + "."
                                    sources.append(source("rendezvous", "ListAgenda", correlation_id, True, "Agenda obtained."))
                                    self._record_tool(db, session.id, user_message.id, "rendezvous", "ListAgenda", correlation_id, "OK", answer)

                                elif intent in {"payment", "consultations", "lab_results", "maternity_record"}:
                                    patient_id, patient_number, _ = _resolve_patient_id(question, request.context, prior_text, user, token)
                                    if not patient_id:
                                        if language == "fr":
                                            answer = "J'ai besoin d'un patient actif dans le contexte de l'écran ou d'un patient_number que vos permissions me permettent de résoudre via Accueil."
                                        else:
                                            answer = "I need an active patient in the screen context or a patient_number that your permissions allow me to resolve through Accueil."
                                    elif intent == "payment":
                                        with grpc.insecure_channel(BILLING_GRPC_TARGET) as channel:
                                            result = billing_pb2_grpc.BillingServiceStub(channel).GetPatientBalance(
                                                billing_pb2.GetPatientBalanceRequest(patient_id=patient_id), metadata=md(token), timeout=3
                                            )
                                        label = patient_number or patient_id
                                        if language == "fr":
                                            answer = f"Solde du patient {label}: {_money_text(result.balance)}; charges {_money_text(result.total_charges)}, payé {_money_text(result.total_paid)}."
                                        else:
                                            answer = f"Patient {label} balance: {_money_text(result.balance)}; charges {_money_text(result.total_charges)}, paid {_money_text(result.total_paid)}."
                                        sources.append(source("billing", "GetPatientBalance", correlation_id, True, "Financial balance obtained."))
                                        self._record_tool(db, session.id, user_message.id, "billing", "GetPatientBalance", correlation_id, "OK", answer)
                                    elif intent == "consultations":
                                        with grpc.insecure_channel(CONSULTATION_GRPC_TARGET) as channel:
                                            result = consultation_pb2_grpc.ConsultationServiceStub(channel).ListPatientConsultations(
                                                consultation_pb2.ListPatientConsultationsRequest(patient_id=patient_id, limit=10, offset=0),
                                                metadata=md(token), timeout=3,
                                            )
                                        latest = result.consultations[0] if result.consultations else None
                                        if language == "fr":
                                            answer = f"{result.total} consultation(s) trouvée(s) pour {patient_number or patient_id}."
                                            if latest:
                                                answer += f" Dernière consultation: {latest.consultation_number}, statut {consultation_pb2.ConsultationStatus.Name(latest.status)}."
                                        else:
                                            answer = f"{result.total} consultation(s) found for {patient_number or patient_id}."
                                            if latest:
                                                answer += f" Latest consultation: {latest.consultation_number}, status {consultation_pb2.ConsultationStatus.Name(latest.status)}."
                                        sources.append(source("consultation", "ListPatientConsultations", correlation_id, True, "Consultation history obtained."))
                                        self._record_tool(db, session.id, user_message.id, "consultation", "ListPatientConsultations", correlation_id, "OK", answer)
                                    elif intent == "lab_results":
                                        with grpc.insecure_channel(LABORATOIRE_GRPC_TARGET) as channel:
                                            result = laboratoire_pb2_grpc.LaboratoireServiceStub(channel).ListPatientLabResults(
                                                laboratoire_pb2.ListPatientLabResultsRequest(patient_id=patient_id, limit=10, offset=0),
                                                metadata=md(token), timeout=3,
                                            )
                                        if language == "fr":
                                            answer = f"{result.total} résultat(s) laboratoire enregistré(s) pour {patient_number or patient_id}."
                                        else:
                                            answer = f"{result.total} laboratory result(s) recorded for {patient_number or patient_id}."
                                        sources.append(source("laboratoire", "ListPatientLabResults", correlation_id, True, "Laboratory-result history obtained."))
                                        self._record_tool(db, session.id, user_message.id, "laboratoire", "ListPatientLabResults", correlation_id, "OK", answer)
                                    elif intent == "maternity_record":
                                        with grpc.insecure_channel(MATERNITE_GRPC_TARGET) as channel:
                                            result = maternite_pb2_grpc.MaterniteServiceStub(channel).GetMaternityRecord(
                                                maternite_pb2.GetMaternityRecordRequest(patient_id=patient_id), metadata=md(token), timeout=3
                                            )
                                        pregnancy = result.record.pregnancy
                                        if language == "fr":
                                            answer = f"Dossier maternité {pregnancy.pregnancy_number}: statut {maternite_pb2.PregnancyStatus.Name(pregnancy.status)}, risque {maternite_pb2.RiskLevel.Name(pregnancy.risk_level)}."
                                        else:
                                            answer = f"Maternity record {pregnancy.pregnancy_number}: status {maternite_pb2.PregnancyStatus.Name(pregnancy.status)}, risk {maternite_pb2.RiskLevel.Name(pregnancy.risk_level)}."
                                        sources.append(source("maternite", "GetMaternityRecord", correlation_id, True, "Maternity record obtained."))
                                        self._record_tool(db, session.id, user_message.id, "maternite", "GetMaternityRecord", correlation_id, "OK", answer)

                                elif intent == "hr_dashboard":
                                    with grpc.insecure_channel(HR_GRPC_TARGET) as channel:
                                        result = hr_pb2_grpc.HRServiceStub(channel).GetHrDashboard(
                                            hr_pb2.HrDashboardRequest(work_date=""), metadata=md(token), timeout=3
                                        )
                                    if language == "fr":
                                        answer = (
                                            f"Présences RH du {result.work_date}: {result.scheduled_today} planifiés, {result.present_today} présents, "
                                            f"{result.late_today} en retard, {result.absent_today} absents, {result.excused_today} excusés; "
                                            f"{result.pending_leave_requests} demande(s) de congé en attente."
                                        )
                                    else:
                                        answer = (
                                            f"HR attendance for {result.work_date}: {result.scheduled_today} scheduled, {result.present_today} present, "
                                            f"{result.late_today} late, {result.absent_today} absent, {result.excused_today} excused; "
                                            f"{result.pending_leave_requests} leave request(s) pending."
                                        )
                                    sources.append(source("hr", "GetHrDashboard", correlation_id, True, "HR dashboard obtained."))
                                    self._record_tool(db, session.id, user_message.id, "hr", "GetHrDashboard", correlation_id, "OK", answer)

                                elif intent == "notifications":
                                    with grpc.insecure_channel(AUTH_GRPC_TARGET) as channel:
                                        result = auth_pb2_grpc.AuthServiceStub(channel).ListNotifications(
                                            auth_pb2.ListNotificationsRequest(
                                                recipient_id=user.id,
                                                page=common_pb2.PageRequest(page=1, page_size=10),
                                            ),
                                            metadata=md(token), timeout=3,
                                        )
                                    unread = [item for item in result.notifications if item.status == auth_pb2.NOTIFICATION_STATUS_UNREAD]
                                    if language == "fr":
                                        answer = f"Vous avez {len(unread)} notification(s) non lue(s) parmi les {len(result.notifications)} plus récentes."
                                    else:
                                        answer = f"You have {len(unread)} unread notification(s) among your {len(result.notifications)} most recent notifications."
                                    sources.append(source("auth", "ListNotifications", correlation_id, True, "User notifications obtained."))
                                    self._record_tool(db, session.id, user_message.id, "auth", "ListNotifications", correlation_id, "OK", answer)

                            except grpc.RpcError as exc:
                                service_name = {
                                    "service_health": "bi", "kpi": "bi", "beds": "hospitalisation", "patient": "accueil",
                                    "stock": "pharmacie", "stock_alerts": "pharmacie", "agenda": "rendezvous",
                                    "payment": "billing", "consultations": "consultation", "lab_results": "laboratoire",
                                    "maternity_record": "maternite", "hr_dashboard": "hr", "notifications": "auth",
                                }.get(intent, "downstream service")
                                answer = _grpc_error_message(language, service_name, exc)
                                sources.append(source(service_name, "downstream", correlation_id, False, f"{exc.code().name}: {exc.details()}"))
                                self._record_tool(db, session.id, user_message.id, service_name, "downstream", correlation_id, f"ERROR:{exc.code().name}", exc.details())

            assistant_message = ChatMessage(session_id=session.id, role="ASSISTANT", content=answer)
            db.add(assistant_message)
            session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(assistant_message)

            logger.info(
                "rpc=AskAssistant peer=%s actor=%s session=%s module=%s intent=%s correlation_id=%s outcome=OK",
                context.peer(), user.id, session.id, module, intent, correlation_id,
            )
            return chatbot_pb2.AskAssistantResponse(
                session=session_proto(session),
                answer_message=message_proto(assistant_message),
                answer=answer,
                intent=intent,
                confidence=confidence,
                sources=sources,
                language=language,
                suggested_questions=build_suggestions(language, permissions, module),
                mode=chatbot_pb2.ASSISTANT_MODE_AUTHENTICATED,
                permission_note=permission_note,
            )
        finally:
            db.close()

    def GetConversation(self, request, context):
        user, _ = auth_user(context)
        db = ChatbotSessionLocal()
        try:
            session = self._get_session(db, request.session_id.strip(), user.id, context)
            limit = min(max(request.limit or 50, 1), 200)
            offset = max(request.offset, 0)
            total = db.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session.id)) or 0
            rows = db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.asc())
                .limit(limit)
                .offset(offset)
            ).all()
            return chatbot_pb2.GetConversationResponse(
                session=session_proto(session), messages=[message_proto(item) for item in rows], total=int(total)
            )
        finally:
            db.close()

    def ClearSession(self, request, context):
        user, _ = auth_user(context)
        db = ChatbotSessionLocal()
        try:
            session = self._get_session(db, request.session_id.strip(), user.id, context)
            tools = db.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.session_id == session.id)) or 0
            messages = db.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session.id)) or 0
            db.execute(delete(ToolCall).where(ToolCall.session_id == session.id))
            db.execute(delete(ChatMessage).where(ChatMessage.session_id == session.id))
            session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            return chatbot_pb2.ClearSessionResponse(
                session_id=session.id, deleted_messages=int(messages), deleted_tool_calls=int(tools)
            )
        finally:
            db.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health("ONLINE", "Chatbot v2 and MySQL are available.")
        except Exception:
            logger.exception("Chatbot HealthCheck degraded")
            return build_health("DEGRADED", "Chatbot v2 is running but MySQL is unavailable.")
