import {
  BedDouble,
  Clock3,
  Hospital,
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
  listAdmissions,
  listHospitalBeds,
} from "../services/hospitalizationService";

import type {
  HospitalBed,
  HospitalizationAdmission,
} from "../types/hospitalization";

function statusLabel(
  status:
    HospitalizationAdmission["status"]
) {
  if (status === "WAITING") {
    return "En attente";
  }

  if (status === "ADMITTED") {
    return "Hospitalisé";
  }

  return "Sorti";
}

export default function HospitalizationPage() {
  const navigate =
    useNavigate();

  const [admissions, setAdmissions] =
    useState<
      HospitalizationAdmission[]
    >([]);

  const [beds, setBeds] =
    useState<HospitalBed[]>([]);

  const [search, setSearch] =
    useState("");

  async function refresh() {
    const [
      admissionData,
      bedData,
    ] = await Promise.all([
      listAdmissions(),
      listHospitalBeds(),
    ]);

    setAdmissions(
      admissionData
    );

    setBeds(
      bedData
    );
  }

  useEffect(() => {
    refresh();
  }, []);

  const waiting =
    admissions.filter(
      (item) =>
        item.status ===
        "WAITING"
    ).length;

  const admitted =
    admissions.filter(
      (item) =>
        item.status ===
        "ADMITTED"
    ).length;

  const availableBeds =
    beds.filter(
      (bed) =>
        !bed
          .occupiedByAdmissionId
    ).length;

  const filtered =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return admissions;
      }

      return admissions.filter(
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
      admissions,
      search,
    ]);

  return (
    <div className="hospitalization-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 02 • HOSPITALISATION
          </p>

          <h1>
            Hospitalisation
          </h1>

          <p className="subtitle">
            Admissions, chambres,
            lits, séjour et sorties.
          </p>
        </div>

        <div className="consultation-live">
          <span className="client-dot" />
          Gestion des lits active
        </div>
      </header>

      <section className="dashboard-stats consultation-stats">
        <article>
          <div className="stat-icon">
            <Clock3 />
          </div>

          <div>
            <span>
              Admissions en attente
            </span>

            <strong>
              {waiting}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Hospital />
          </div>

          <div>
            <span>
              Patients hospitalisés
            </span>

            <strong>
              {admitted}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <BedDouble />
          </div>

          <div>
            <span>
              Lits disponibles
            </span>

            <strong>
              {availableBeds}
              /{beds.length}
            </strong>
          </div>
        </article>
      </section>

      <section className="consultation-list-card">
        <div className="panel-heading">
          <div>
            <span className="section-label">
              GESTION DES ADMISSIONS
            </span>

            <h2>
              Patients
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
          <table className="patient-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Numéro</th>
                <th>Motif</th>
                <th>Statut</th>
                <th>Unité</th>
                <th>Chambre / Lit</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map(
                (admission) => (
                  <tr
                    key={
                      admission.id
                    }
                  >
                    <td>
                      <div className="patient-name">
                        <div className="patient-avatar">
                          {admission.patientName
                            .charAt(0)
                            .toUpperCase()}
                        </div>

                        <strong>
                          {
                            admission.patientName
                          }
                        </strong>
                      </div>
                    </td>

                    <td>
                      <code>
                        {
                          admission.patientNumber
                        }
                      </code>
                    </td>

                    <td>
                      {
                        admission.reason
                      }
                    </td>

                    <td>
                      <span
                        className={`hospitalization-status ${admission.status.toLowerCase()}`}
                      >
                        {statusLabel(
                          admission.status
                        )}
                      </span>
                    </td>

                    <td>
                      {admission.ward ??
                        "—"}
                    </td>

                    <td>
                      {admission.roomNumber
                        ? `${admission.roomNumber} / ${admission.bedNumber}`
                        : "—"}
                    </td>

                    <td>
                      <button
                        className="table-action consultation-open"
                        onClick={() =>
                          navigate(
                            `/hospitalisation/${admission.id}`
                          )
                        }
                      >
                        {admission.status ===
                        "WAITING"
                          ? "Admettre"
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
                    Aucune demande
                    d'hospitalisation.
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
