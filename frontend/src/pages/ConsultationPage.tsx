import {
  CheckCircle2,
  Clock3,
  PlayCircle,
  Search,
  Stethoscope,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import {
  listConsultations,
  startConsultation,
} from "../services/consultationService";

import type {
  Consultation,
} from "../types/consultation";

function statusLabel(
  status: Consultation["status"]
) {
  if (status === "WAITING") {
    return "En attente";
  }

  if (status === "IN_PROGRESS") {
    return "En cours";
  }

  return "Terminée";
}

export default function ConsultationPage() {
  const navigate = useNavigate();

  const [consultations, setConsultations] =
    useState<Consultation[]>([]);

  const [search, setSearch] =
    useState("");

  async function refresh() {
    const data =
      await listConsultations();

    setConsultations(data);
  }

  useEffect(() => {
    refresh();
  }, []);

  const waiting =
    consultations.filter(
      (item) =>
        item.status === "WAITING"
    );

  const inProgress =
    consultations.filter(
      (item) =>
        item.status === "IN_PROGRESS"
    );

  const completed =
    consultations.filter(
      (item) =>
        item.status === "COMPLETED"
    );

  const filtered =
    useMemo(() => {
      const value =
        search.trim().toLowerCase();

      if (!value) {
        return consultations;
      }

      return consultations.filter(
        (item) =>
          item.patientName
            .toLowerCase()
            .includes(value) ||
          item.patientNumber
            .toLowerCase()
            .includes(value) ||
          item.reason
            .toLowerCase()
            .includes(value)
      );
    }, [
      consultations,
      search,
    ]);

  async function handleOpen(
    consultation: Consultation
  ) {
    if (
      consultation.status ===
      "WAITING"
    ) {
      await startConsultation(
        consultation.id
      );
    }

    navigate(
      `/consultation/${consultation.id}`
    );
  }

  return (
    <div className="consultation-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 04 • CONSULTATION
          </p>

          <h1>
            Consultation médicale
          </h1>

          <p className="subtitle">
            File médicale, examen,
            diagnostic, ordonnance et
            décisions cliniques.
          </p>
        </div>

        <div className="consultation-live">
          <span className="client-dot" />
          File synchronisée
        </div>
      </header>

      <section className="dashboard-stats consultation-stats">
        <article>
          <div className="stat-icon">
            <Clock3 />
          </div>

          <div>
            <span>
              En attente
            </span>

            <strong>
              {waiting.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Stethoscope />
          </div>

          <div>
            <span>
              En consultation
            </span>

            <strong>
              {inProgress.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <CheckCircle2 />
          </div>

          <div>
            <span>
              Terminées
            </span>

            <strong>
              {completed.length}
            </strong>
          </div>
        </article>
      </section>

      <section className="consultation-list-card">
        <div className="panel-heading">
          <div>
            <span className="section-label">
              FILE MÉDICALE
            </span>

            <h2>
              Patients à consulter
            </h2>
          </div>

          <div className="patient-search">
            <Search size={17} />

            <input
              value={search}
              onChange={(event) =>
                setSearch(
                  event.target.value
                )
              }
              placeholder="Patient, numéro, motif..."
            />
          </div>
        </div>

        <div className="patient-table-wrapper">
          <table className="patient-table consultation-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Numéro</th>
                <th>Motif</th>
                <th>Statut</th>
                <th>Laboratoire</th>
                <th>Hospitalisation</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map(
                (consultation) => (
                  <tr
                    key={
                      consultation.id
                    }
                  >
                    <td>
                      <div className="patient-name">
                        <div className="patient-avatar">
                          {consultation.patientName
                            .charAt(0)
                            .toUpperCase()}
                        </div>

                        <strong>
                          {
                            consultation.patientName
                          }
                        </strong>
                      </div>
                    </td>

                    <td>
                      <code>
                        {
                          consultation.patientNumber
                        }
                      </code>
                    </td>

                    <td>
                      {
                        consultation.reason
                      }
                    </td>

                    <td>
                      <span
                        className={`consultation-status ${consultation.status.toLowerCase()}`}
                      >
                        {statusLabel(
                          consultation.status
                        )}
                      </span>
                    </td>

                    <td>
                      {consultation.laboratoryRequested
                        ? "Demandé"
                        : "—"}
                    </td>

                    <td>
                      {consultation.hospitalizationRequested
                        ? "Demandée"
                        : "—"}
                    </td>

                    <td>
                      <button
                        className="table-action consultation-open"
                        onClick={() =>
                          handleOpen(
                            consultation
                          )
                        }
                      >
                        <PlayCircle
                          size={14}
                        />

                        {consultation.status ===
                        "WAITING"
                          ? "Commencer"
                          : "Ouvrir"}
                      </button>
                    </td>
                  </tr>
                )
              )}

              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="empty-table"
                  >
                    Aucun patient dans
                    la file de consultation.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
