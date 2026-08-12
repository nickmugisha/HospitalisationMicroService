import {
  ArrowLeft,
  BedDouble,
  DoorOpen,
  Hospital,
  LogOut,
} from "lucide-react";

import {
  useEffect,
  useState,
} from "react";

import {
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  admitPatient,
  dischargePatient,
  getAdmission,
  listHospitalBeds,
} from "../services/hospitalizationService";

import type {
  HospitalBed,
  HospitalizationAdmission,
} from "../types/hospitalization";

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

export default function HospitalizationDetailPage() {
  const navigate =
    useNavigate();

  const { admissionId } =
    useParams();

  const [admission, setAdmission] =
    useState<
      HospitalizationAdmission | null
    >(null);

  const [beds, setBeds] =
    useState<HospitalBed[]>([]);

  const [selectedBed, setSelectedBed] =
    useState("");

  const [admissionNotes, setAdmissionNotes] =
    useState("");

  const [dischargeNotes, setDischargeNotes] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  async function load() {
    if (!admissionId) {
      return;
    }

    const [
      admissionData,
      bedData,
    ] = await Promise.all([
      getAdmission(
        admissionId
      ),
      listHospitalBeds(),
    ]);

    setAdmission(
      admissionData
    );

    setBeds(
      bedData
    );

    const firstAvailable =
      bedData.find(
        (bed) =>
          !bed
            .occupiedByAdmissionId
      );

    if (firstAvailable) {
      setSelectedBed(
        firstAvailable.id
      );
    }

    setLoading(false);
  }

  useEffect(() => {
    load();
  }, [admissionId]);

  async function handleAdmission() {
    if (
      !admission ||
      !selectedBed
    ) {
      return;
    }

    const updated =
      await admitPatient(
        admission.id,
        selectedBed,
        admissionNotes
      );

    setAdmission(updated);

    setBeds(
      await listHospitalBeds()
    );
  }

  async function handleDischarge() {
    if (!admission) {
      return;
    }

    const updated =
      await dischargePatient(
        admission.id,
        dischargeNotes
      );

    setAdmission(updated);

    setBeds(
      await listHospitalBeds()
    );
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement...
      </div>
    );
  }

  if (!admission) {
    return (
      <div className="patient-detail-state">
        Admission introuvable.
      </div>
    );
  }

  const availableBeds =
    beds.filter(
      (bed) =>
        !bed.occupiedByAdmissionId
    );

  return (
    <div className="hospitalization-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate(
            "/hospitalisation"
          )
        }
      >
        <ArrowLeft size={17} />
        Retour aux admissions
      </button>

      <section className="medical-header">
        <div>
          <p className="eyebrow">
            DOSSIER D'HOSPITALISATION
          </p>

          <h1>
            {admission.patientName}
          </h1>

          <div className="profile-meta">
            <span>
              {
                admission.patientNumber
              }
            </span>

            <span>
              {admission.reason}
            </span>
          </div>
        </div>

        <span
          className={`hospitalization-status ${admission.status.toLowerCase()}`}
        >
          {admission.status ===
          "WAITING"
            ? "En attente"
            : admission.status ===
                "ADMITTED"
              ? "Hospitalisé"
              : "Sorti"}
        </span>
      </section>

      <section className="hospital-stay-grid">
        <article className="medical-card">
          <span className="section-label">
            DEMANDE
          </span>

          <h2>
            Informations d'admission
          </h2>

          <div className="hospital-info-list">
            <div>
              <span>
                Motif
              </span>

              <strong>
                {admission.reason}
              </strong>
            </div>

            <div>
              <span>
                Demandée le
              </span>

              <strong>
                {formatDate(
                  admission.requestedAt
                )}
              </strong>
            </div>

            <div>
              <span>
                Admis le
              </span>

              <strong>
                {formatDate(
                  admission.admittedAt
                )}
              </strong>
            </div>

            <div>
              <span>
                Sorti le
              </span>

              <strong>
                {formatDate(
                  admission.dischargedAt
                )}
              </strong>
            </div>
          </div>
        </article>

        <article className="medical-card">
          <span className="section-label">
            EMPLACEMENT
          </span>

          <h2>
            Chambre & lit
          </h2>

          {admission.status ===
          "WAITING" ? (
            <>
              <label className="medical-label">
                Lit disponible

                <select
                  className="hospital-select"
                  value={
                    selectedBed
                  }
                  onChange={(event) =>
                    setSelectedBed(
                      event.target.value
                    )
                  }
                >
                  {availableBeds.map(
                    (bed) => (
                      <option
                        value={bed.id}
                        key={bed.id}
                      >
                        {bed.ward}
                        {" • Chambre "}
                        {
                          bed.roomNumber
                        }
                        {" • Lit "}
                        {
                          bed.bedNumber
                        }
                      </option>
                    )
                  )}
                </select>
              </label>

              <label className="medical-label">
                Notes d'admission

                <textarea
                  value={
                    admissionNotes
                  }
                  onChange={(event) =>
                    setAdmissionNotes(
                      event.target.value
                    )
                  }
                  placeholder="Instructions ou observations..."
                />
              </label>

              <button
                className="primary-action hospital-admit"
                onClick={
                  handleAdmission
                }
                disabled={
                  !selectedBed
                }
              >
                <BedDouble
                  size={17}
                />
                Admettre le patient
              </button>
            </>
          ) : (
            <div className="assigned-bed">
              <Hospital />

              <div>
                <span>
                  {
                    admission.ward
                  }
                </span>

                <strong>
                  Chambre{" "}
                  {
                    admission.roomNumber
                  }{" "}
                  • Lit{" "}
                  {
                    admission.bedNumber
                  }
                </strong>
              </div>
            </div>
          )}
        </article>
      </section>

      {admission.status ===
        "ADMITTED" && (
        <section className="medical-card discharge-card">
          <div className="decision-icon">
            <DoorOpen />
          </div>

          <div>
            <span className="section-label">
              SORTIE
            </span>

            <h2>
              Terminer l'hospitalisation
            </h2>

            <label className="medical-label">
              Résumé / recommandations

              <textarea
                value={
                  dischargeNotes
                }
                onChange={(event) =>
                  setDischargeNotes(
                    event.target.value
                  )
                }
                placeholder="État du patient, recommandations..."
              />
            </label>

            <button
              className="secondary-action hospital-discharge"
              onClick={
                handleDischarge
              }
            >
              <LogOut size={17} />
              Enregistrer la sortie
            </button>
          </div>
        </section>
      )}

      {admission.status ===
        "DISCHARGED" && (
        <section className="medical-card discharge-summary">
          <span className="section-label">
            HOSPITALISATION TERMINÉE
          </span>

          <h2>
            Résumé de sortie
          </h2>

          <p>
            {admission.dischargeNotes ||
              "Aucune note de sortie."}
          </p>
        </section>
      )}
    </div>
  );
}
