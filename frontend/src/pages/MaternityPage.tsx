import {
  Baby,
  Clock3,
  HeartPulse,
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
  listMaternityCases,
} from "../services/maternityService";

import type {
  MaternityCase,
} from "../types/maternity";

function statusLabel(
  status:
    MaternityCase["status"]
) {
  switch (status) {
    case "WAITING":
      return "En attente";

    case "ADMITTED":
      return "Admise";

    case "IN_LABOR":
      return "En travail";

    case "DELIVERED":
      return "Accouchée";

    case "DISCHARGED":
      return "Sortie";
  }
}

function formatDate(
  value?: string
) {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      dateStyle: "medium",
      timeStyle: "short",
    }
  ).format(
    new Date(value)
  );
}

export default function MaternityPage() {
  const navigate =
    useNavigate();

  const [cases, setCases] =
    useState<MaternityCase[]>([]);

  const [search, setSearch] =
    useState("");

  async function refresh() {
    setCases(
      await listMaternityCases()
    );
  }

  useEffect(() => {
    refresh();
  }, []);

  const filtered =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return cases;
      }

      return cases.filter(
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
      cases,
      search,
    ]);

  const waiting =
    cases.filter(
      (item) =>
        item.status ===
        "WAITING"
    ).length;

  const hospitalized =
    cases.filter(
      (item) =>
        item.status ===
          "ADMITTED" ||
        item.status ===
          "IN_LABOR"
    ).length;

  const delivered =
    cases.filter(
      (item) =>
        item.status ===
          "DELIVERED" ||
        item.status ===
          "DISCHARGED"
    ).length;

  return (
    <div className="maternity-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 07 • MATERNITÉ
          </p>

          <h1>
            Maternité
          </h1>

          <p className="subtitle">
            Grossesse, admission,
            travail, accouchement,
            nouveau-né et sortie.
          </p>
        </div>

        <div className="consultation-live">
          <span className="client-dot" />
          Parcours obstétrical actif
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
              {waiting}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <HeartPulse />
          </div>

          <div>
            <span>
              Prises en charge
            </span>

            <strong>
              {hospitalized}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Baby />
          </div>

          <div>
            <span>
              Accouchements
            </span>

            <strong>
              {delivered}
            </strong>
          </div>
        </article>
      </section>

      <section className="consultation-list-card">
        <div className="panel-heading">
          <div>
            <span className="section-label">
              DOSSIERS MATERNITÉ
            </span>

            <h2>
              Patientes
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
              placeholder="Patiente, numéro, motif..."
            />
          </div>
        </div>

        <div className="patient-table-wrapper">
          <table className="patient-table">
            <thead>
              <tr>
                <th>Patiente</th>
                <th>Numéro</th>
                <th>Motif</th>
                <th>Grossesse</th>
                <th>Statut</th>
                <th>Admission</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map(
                (item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="patient-name">
                        <div className="patient-avatar maternity-avatar">
                          <Baby
                            size={16}
                          />
                        </div>

                        <strong>
                          {
                            item.patientName
                          }
                        </strong>
                      </div>
                    </td>

                    <td>
                      <code>
                        {
                          item.patientNumber
                        }
                      </code>
                    </td>

                    <td>
                      {item.reason}
                    </td>

                    <td>
                      {item.gestationalAgeWeeks
                        ? `${item.gestationalAgeWeeks} semaines`
                        : "—"}
                    </td>

                    <td>
                      <span
                        className={`maternity-status ${item.status.toLowerCase()}`}
                      >
                        {statusLabel(
                          item.status
                        )}
                      </span>
                    </td>

                    <td>
                      {formatDate(
                        item.admittedAt
                      )}
                    </td>

                    <td>
                      <button
                        className="table-action"
                        onClick={() =>
                          navigate(
                            `/maternite/${item.id}`
                          )
                        }
                      >
                        {item.status ===
                        "WAITING"
                          ? "Prendre en charge"
                          : "Ouvrir"}
                      </button>
                    </td>
                  </tr>
                )
              )}

              {filtered.length ===
                0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="empty-table"
                  >
                    Aucun dossier maternité.
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
