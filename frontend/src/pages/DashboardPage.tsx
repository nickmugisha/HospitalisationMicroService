import {
  Database,
  RefreshCw,
  Server,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import {
  useEffect,
  useState,
} from "react";

import { modules } from "../config/modules";
import { getSystemHealth } from "../services/systemService";
import type { SystemHealth } from "../types/system";

export default function DashboardPage() {
  const [health, setHealth] =
    useState<SystemHealth | null>(null);

  const [loading, setLoading] =
    useState(true);

  async function loadHealth() {
    setLoading(true);

    try {
      setHealth(
        await getSystemHealth()
      );
    } catch {
      setHealth({
        online: false,
        status: "OFFLINE",
        server_name: null,
        target: "Gateway local",
        message:
          "Impossible de contacter le Gateway FastAPI.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHealth();
  }, []);

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">
            PLATEFORME HOSPITALIÈRE DISTRIBUÉE
          </p>

          <h1>Centre de supervision</h1>

          <p className="subtitle">
            Vue générale de l'infrastructure
            et des services hospitaliers.
          </p>
        </div>

        <button
          className="refresh-button"
          onClick={loadHealth}
          disabled={loading}
        >
          <RefreshCw
            size={18}
            className={
              loading ? "spin" : ""
            }
          />

          {loading
            ? "Vérification..."
            : "Actualiser"}
        </button>
      </header>

      <section className="dashboard-stats">
        <article>
          <div className="stat-icon">
            <Workflow />
          </div>

          <div>
            <span>Microservices</span>
            <strong>11</strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Server />
          </div>

          <div>
            <span>Serveur</span>
            <strong>
              {health?.online
                ? "Online"
                : "Offline"}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <ShieldCheck />
          </div>

          <div>
            <span>Architecture</span>
            <strong>gRPC</strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Database />
          </div>

          <div>
            <span>Accès DB client</span>
            <strong>Interdit</strong>
          </div>
        </article>
      </section>

      <section className="server-card">
        <div className="server-heading">
          <div>
            <span className="section-label">
              INFRASTRUCTURE
            </span>

            <h2>Serveur central Windows</h2>
          </div>

          <span
            className={`status ${
              health?.online
                ? "online"
                : "offline"
            }`}
          >
            <span className="status-dot" />

            {loading
              ? "CONNEXION..."
              : health?.online
                ? "ONLINE"
                : "OFFLINE"}
          </span>
        </div>

        <div className="server-details">
          <div>
            <span>Adresse</span>
            <strong>
              {health?.target ??
                "10.139.91.95:50051"}
            </strong>
          </div>

          <div>
            <span>Serveur</span>
            <strong>
              {health?.server_name ??
                "Non disponible"}
            </strong>
          </div>

          <div>
            <span>Protocole</span>
            <strong>gRPC</strong>
          </div>
        </div>

        <div className="server-message">
          {health?.message ??
            "Vérification du serveur..."}
        </div>
      </section>

      <section className="modules-section">
        <div className="section-header">
          <div>
            <span className="section-label">
              SERVICES
            </span>

            <h2>
              Architecture fonctionnelle
            </h2>
          </div>

          <span className="module-count">
            11 services
          </span>
        </div>

        <div className="module-grid">
          {modules
            .filter(
              (module) =>
                module.id !== "dashboard"
            )
            .map(
              (
                { id, label, icon: Icon },
                index
              ) => (
                <article
                  className="module-card"
                  key={id}
                >
                  <span className="module-number">
                    {String(index + 1).padStart(
                      2,
                      "0"
                    )}
                  </span>

                  <div className="module-icon">
                    <Icon size={24} />
                  </div>

                  <h3>{label}</h3>

                  <p>
                    Interface métier préparée pour
                    la communication gRPC.
                  </p>

                  <div className="module-footer">
                    <span className="development-dot" />
                    PRÊT POUR INTÉGRATION
                  </div>
                </article>
              )
            )}
        </div>
      </section>
    </>
  );
}
