import {
  CheckCircle2,
  Clock3,
  FlaskConical,
  Microscope,
  Search,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  listLaboratoryRequests,
} from "../services/laboratoryService";

import type {
  LaboratoryRequest,
} from "../types/laboratory";

function statusText(
  status: LaboratoryRequest["status"]
) {
  switch (status) {
    case "WAITING":
      return "En attente";

    case "SAMPLE_COLLECTED":
      return "Prélevé";

    case "IN_ANALYSIS":
      return "En analyse";

    case "COMPLETED":
      return "Terminé";
  }
}

export default function LaboratoryPage() {
  const navigate =
    useNavigate();

  const [requests, setRequests] =
    useState<LaboratoryRequest[]>([]);

  const [search, setSearch] =
    useState("");

  async function refresh() {
    setRequests(
      await listLaboratoryRequests()
    );
  }

  useEffect(() => {
    refresh();
  }, []);

  const filtered =
    useMemo(() => {
      const value =
        search.trim().toLowerCase();

      if (!value) {
        return requests;
      }

      return requests.filter(
        (request) =>
          request.patientName
            .toLowerCase()
            .includes(value) ||
          request.patientNumber
            .toLowerCase()
            .includes(value) ||
          request.requestNotes
            .toLowerCase()
            .includes(value)
      );
    }, [
      requests,
      search,
    ]);

  const waiting =
    requests.filter(
      (request) =>
        request.status === "WAITING"
    ).length;

  const processing =
    requests.filter(
      (request) =>
        request.status ===
          "SAMPLE_COLLECTED" ||
        request.status ===
          "IN_ANALYSIS"
    ).length;

  const completed =
    requests.filter(
      (request) =>
        request.status === "COMPLETED"
    ).length;

  return (
    <div className="laboratory-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 05 • LABORATOIRE
          </p>

          <h1>
            Laboratoire médical
          </h1>

          <p className="subtitle">
            Demandes d'analyses,
            prélèvements, traitement et
            validation des résultats.
          </p>
        </div>

        <div className="consultation-live">
          <span className="client-dot" />
          Demandes synchronisées
        </div>
      </header>

      <section className="dashboard-stats consultation-stats">
        <article>
          <div className="stat-icon">
            <Clock3 />
          </div>

          <div>
            <span>En attente</span>
            <strong>{waiting}</strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Microscope />
          </div>

          <div>
            <span>
              En traitement
            </span>

            <strong>
              {processing}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <CheckCircle2 />
          </div>

          <div>
            <span>Terminées</span>
            <strong>
              {completed}
            </strong>
          </div>
        </article>
      </section>

      <section className="consultation-list-card">
        <div className="panel-heading">
          <div>
            <span className="section-label">
              DEMANDES D'ANALYSES
            </span>

            <h2>
              File laboratoire
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
              placeholder="Patient, numéro, analyse..."
            />
          </div>
        </div>

        <div className="patient-table-wrapper">
          <table className="patient-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Numéro</th>
                <th>Demande</th>
                <th>Statut</th>
                <th>Analyses</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map(
                (request) => (
                  <tr key={request.id}>
                    <td>
                      <div className="patient-name">
                        <div className="patient-avatar">
                          {request.patientName
                            .charAt(0)
                            .toUpperCase()}
                        </div>

                        <strong>
                          {request.patientName}
                        </strong>
                      </div>
                    </td>

                    <td>
                      <code>
                        {
                          request.patientNumber
                        }
                      </code>
                    </td>

                    <td>
                      {
                        request.requestNotes
                      }
                    </td>

                    <td>
                      <span
                        className={`laboratory-status ${request.status.toLowerCase()}`}
                      >
                        {statusText(
                          request.status
                        )}
                      </span>
                    </td>

                    <td>
                      {
                        request.tests.length
                      }
                    </td>

                    <td>
                      <button
                        className="table-action consultation-open"
                        onClick={() =>
                          navigate(
                            `/laboratoire/${request.id}`
                          )
                        }
                      >
                        <FlaskConical
                          size={14}
                        />
                        Ouvrir
                      </button>
                    </td>
                  </tr>
                )
              )}

              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="empty-table"
                  >
                    Aucune demande
                    laboratoire.
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
