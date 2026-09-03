# ProjectX Chatbot v2 — Server → Linux client handoff

## Service

- gRPC service: `hospital.chatbot.v1.ChatbotService`
- port: `50061`
- contract: `proto/chatbot/v1/chatbot.proto`

## Login page — public mode

Call `GetPublicWelcome(locale)` when the login assistant opens.

Call `AskPublicAssistant(question, locale, correlation_id)` for login-page questions.

**Do not attach a Bearer token to public mode.** The server does not use public mode to access hospital data.

Public mode can explain ProjectX/login/QR basics. It refuses patient, clinical, HR and financial data.

## After authentication

Call `StartSession` with the normal JWT in gRPC metadata:

```text
authorization: Bearer <ACCESS_TOKEN>
```

`StartSession` returns the assistant greeting. Display `welcome_message`; do not manufacture the user's name on the client.

## Context passed from client

For `StartSession` and `AskAssistant`, populate `AssistantContext` when the information already exists in React/FastAPI:

```text
current_module
current_route
active_patient_id
active_patient_number
active_consultation_id
active_admission_id
active_invoice_id
active_employee_id
locale
```

Important: these are conversational hints only. Never send client-invented roles/permissions because Chatbot gets those from Auth by validating the JWT.

Examples of `current_module`:

```text
accueil
consultation
laboratoire
pharmacie
hospitalisation
billing
maternite
rendezvous
bi
hr
auth
```

## AskAssistant response

In addition to the existing fields, consume:

```text
language
suggested_questions
mode
permission_note
```

- `language`: `en` or `fr`
- `suggested_questions`: safe prompts appropriate to current module/permissions
- `mode`: public/authenticated marker
- `permission_note`: explains the permission state for procedure/denied-data questions

## Security rule

The current page is context, not authority.

The server derives identity, roles and permissions from Auth. A user cannot gain Billing/HR/clinical access by sending a different `current_module`.

## Error handling

Preserve gRPC errors such as:

- `INVALID_ARGUMENT`
- `UNAUTHENTICATED`
- `PERMISSION_DENIED`
- `NOT_FOUND`
- `UNAVAILABLE`
- `RESOURCE_EXHAUSTED` (public assistant rate limit)

Do not turn a failed gRPC call into a fake successful chatbot answer.
