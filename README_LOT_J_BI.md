# ProjectX LOT J — BI & Statistique

Service gRPC BI on port 50060. It aggregates business KPIs only through existing gRPC APIs; it never reads another service's MySQL schema. The service stores only its own optional metric snapshots and report-run metadata in `hospital_bi`.

Expected service-health behavior before LOT K: the chatbot on 50061 is reported OFFLINE. That makes Dashboard quality PARTIAL rather than inventing availability.
