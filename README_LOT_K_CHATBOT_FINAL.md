# ProjectX LOT K — Chatbot + final runtime

Adds the final gRPC service on port 50061 and its own `hospital_chatbot` database.
The assistant uses deterministic intent routing and calls hospital services through gRPC only; it never reads another service's MySQL database.

Implemented intents:
- patient -> Accueil
- beds -> Hospitalisation
- stock -> Pharmacie
- agenda -> Rendez-vous
- payment -> Billing (+ Accueil identity resolution)
- KPI -> BI
- service health -> BI

Security:
- Every Chatbot RPC requires a valid JWT and `chatbot.ask`.
- Each intent also checks the underlying business permission.
- Downstream calls propagate the user's Bearer token.
- Downstream failure is reported as failure; the chatbot never fabricates success.

This overlay also adds an Auth runtime subclass that supplies `HealthCheck` without changing the validated Login/ValidateToken implementation, plus start/stop-all and global-health scripts for the 11-service demo.
