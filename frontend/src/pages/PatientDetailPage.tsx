import {
  ArrowLeft,
  Baby,
  CalendarDays,
  Edit3,
  FlaskConical,
  Hospital,
  Mail,
  MapPin,
  Phone,
  ShieldAlert,
  Stethoscope,
  UserRound,
  X,
} from "lucide-react";

import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import {
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  getPatientById,
  sendPatientToService,
  updatePatient,
} from "../services/patientService";

import type {
  CreatePatientInput,
  Patient,
  PatientSex,
} from "../types/patient";

function calculateAge(
  birthDate: string
) {
  if (!birthDate) {
    return "—";
  }

  const birth =
    new Date(birthDate);

  const today =
    new Date();

  let age =
    today.getFullYear() -
    birth.getFullYear();

  const month =
    today.getMonth() -
    birth.getMonth();

  if (
    month < 0 ||
    (
      month === 0 &&
      today.getDate() <
        birth.getDate()
    )
  ) {
    age--;
  }

  return `${age} ans`;
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
  ).format(new Date(value));
}

export default function PatientDetailPage() {
  const navigate =
    useNavigate();

  const { patientId } =
    useParams();

  const [patient, setPatient] =
    useState<Patient | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [showEdit, setShowEdit] =
    useState(false);

  const [form, setForm] =
    useState<CreatePatientInput | null>(
      null
    );

  async function loadPatient() {
    if (!patientId) {
      return;
    }

    setLoading(true);

    const result =
      await getPatientById(
        patientId
      );

    setPatient(result);

    if (result) {
      setForm({
        firstName:
          result.firstName,

        lastName:
          result.lastName,

        sex:
          result.sex,

        birthDate:
          result.birthDate,

        phone:
          result.phone,

        email:
          result.email ?? "",

        address:
          result.address,

        emergencyContact:
          result.emergencyContact,
      });
    }

    setLoading(false);
  }

  useEffect(() => {
    loadPatient();
  }, [patientId]);

  async function handleSend(
    service: string
  ) {
    if (!patient) {
      return;
    }

    const updated =
      await sendPatientToService(
        patient.id,
        service
      );

    setPatient(updated);
  }

  async function handleUpdate(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (
      !patient ||
      !form
    ) {
      return;
    }

    const updated =
      await updatePatient(
        patient.id,
        form
      );

    setPatient(updated);
    setShowEdit(false);
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement du dossier...
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="patient-detail-state">
        <h2>
          Patient introuvable
        </h2>

        <button
          className="primary-action"
          onClick={() =>
            navigate("/accueil")
          }
        >
          Retour à l'accueil
        </button>
      </div>
    );
  }

  return (
    <div className="patient-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate("/accueil")
        }
      >
        <ArrowLeft size={17} />
        Retour aux patients
      </button>

      <section className="patient-profile-hero">
        <div className="profile-main">
          <div className="profile-avatar">
            {patient.firstName
              .charAt(0)
              .toUpperCase()}
          </div>

          <div>
            <p className="eyebrow">
              DOSSIER PATIENT
            </p>

            <h1>
              {patient.firstName}{" "}
              {patient.lastName}
            </h1>

            <div className="profile-meta">
              <span>
                {patient.patientNumber}
              </span>

              <span>
                {patient.sex === "M"
                  ? "Masculin"
                  : "Féminin"}
              </span>

              <span>
                {calculateAge(
                  patient.birthDate
                )}
              </span>
            </div>
          </div>
        </div>

        <div className="profile-actions">
          <span
            className={`arrival-badge ${patient.arrivalStatus.toLowerCase()}`}
          >
            {patient.arrivalStatus ===
            "NONE"
              ? "Pas arrivé"
              : patient.arrivalStatus ===
                  "WAITING"
                ? "En attente"
                : "Orienté"}
          </span>

          <button
            className="secondary-action"
            onClick={() =>
              setShowEdit(true)
            }
          >
            <Edit3 size={16} />
            Modifier
          </button>
        </div>
      </section>

      <section className="patient-detail-grid">
        <article className="patient-info-card">
          <div className="detail-card-header">
            <div>
              <span className="section-label">
                IDENTITÉ
              </span>

              <h2>
                Informations patient
              </h2>
            </div>

            <UserRound size={22} />
          </div>

          <div className="patient-information-list">
            <div>
              <CalendarDays />
              <span>
                Date de naissance
              </span>
              <strong>
                {patient.birthDate ||
                  "Non renseignée"}
              </strong>
            </div>

            <div>
              <Phone />
              <span>
                Téléphone
              </span>
              <strong>
                {patient.phone ||
                  "Non renseigné"}
              </strong>
            </div>

            <div>
              <Mail />
              <span>
                Email
              </span>
              <strong>
                {patient.email ||
                  "Non renseigné"}
              </strong>
            </div>

            <div>
              <MapPin />
              <span>
                Adresse
              </span>
              <strong>
                {patient.address ||
                  "Non renseignée"}
              </strong>
            </div>

            <div>
              <ShieldAlert />
              <span>
                Contact d'urgence
              </span>
              <strong>
                {patient.emergencyContact ||
                  "Non renseigné"}
              </strong>
            </div>
          </div>
        </article>

        <article className="patient-current-card">
          <span className="section-label">
            SITUATION ACTUELLE
          </span>

          <h2>
            Parcours courant
          </h2>

          <div className="current-service-box">
            <span>
              Service actuel
            </span>

            <strong>
              {patient.targetService ??
                "Aucun service"}
            </strong>
          </div>

          <div className="current-service-box">
            <span>
              Motif
            </span>

            <strong>
              {patient.arrivalReason ??
                "Non renseigné"}
            </strong>
          </div>

          <div className="current-service-box">
            <span>
              Statut administratif
            </span>

            <strong>
              {patient.status}
            </strong>
          </div>
        </article>
      </section>

      <section className="patient-routing-section">
        <div className="section-header">
          <div>
            <span className="section-label">
              PARCOURS PATIENT
            </span>

            <h2>
              Envoyer vers un service
            </h2>
          </div>
        </div>

        <div className="routing-grid">
          <button
            onClick={() =>
              handleSend(
                "Consultation"
              )
            }
          >
            <Stethoscope />
            <strong>
              Consultation
            </strong>
            <span>
              Évaluation médicale
            </span>
          </button>

          <button
            onClick={() =>
              handleSend(
                "Laboratoire"
              )
            }
          >
            <FlaskConical />
            <strong>
              Laboratoire
            </strong>
            <span>
              Analyses médicales
            </span>
          </button>

          <button
            onClick={() =>
              handleSend(
                "Hospitalisation"
              )
            }
          >
            <Hospital />
            <strong>
              Hospitalisation
            </strong>
            <span>
              Admission et lit
            </span>
          </button>

          <button
            onClick={() =>
              handleSend(
                "Maternité"
              )
            }
          >
            <Baby />
            <strong>
              Maternité
            </strong>
            <span>
              Prise en charge obstétricale
            </span>
          </button>
        </div>
      </section>

      <section className="patient-history-card">
        <div className="section-header">
          <div>
            <span className="section-label">
              TRAÇABILITÉ
            </span>

            <h2>
              Historique du patient
            </h2>
          </div>

          <span className="module-count">
            {patient.history?.length ??
              0}{" "}
            événements
          </span>
        </div>

        <div className="history-timeline">
          {patient.history &&
          patient.history.length > 0 ? (
            patient.history.map(
              (event) => (
                <div
                  className="history-item"
                  key={event.id}
                >
                  <div className="history-dot" />

                  <div className="history-content">
                    <div className="history-title">
                      <strong>
                        {event.label}
                      </strong>

                      <span>
                        {formatDate(
                          event.at
                        )}
                      </span>
                    </div>

                    {event.service && (
                      <small>
                        Service :{" "}
                        {event.service}
                      </small>
                    )}

                    {event.note && (
                      <p>
                        {event.note}
                      </p>
                    )}
                  </div>
                </div>
              )
            )
          ) : (
            <div className="empty-history">
              Aucun événement enregistré.
            </div>
          )}
        </div>
      </section>

      {showEdit && form && (
        <div className="modal-backdrop">
          <form
            className="patient-modal"
            onSubmit={handleUpdate}
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  MODIFICATION
                </span>

                <h2>
                  Modifier le patient
                </h2>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setShowEdit(false)
                }
              >
                <X size={20} />
              </button>
            </div>

            <div className="form-grid">
              <label>
                Prénom
                <input
                  value={
                    form.firstName
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      firstName:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Nom
                <input
                  value={
                    form.lastName
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      lastName:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Sexe
                <select
                  value={form.sex}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      sex:
                        event.target
                          .value as PatientSex,
                    })
                  }
                >
                  <option value="M">
                    Masculin
                  </option>

                  <option value="F">
                    Féminin
                  </option>
                </select>
              </label>

              <label>
                Date de naissance
                <input
                  type="date"
                  value={
                    form.birthDate
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      birthDate:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Téléphone
                <input
                  value={form.phone}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      phone:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Email
                <input
                  type="email"
                  value={
                    form.email ?? ""
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      email:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Adresse
                <input
                  value={
                    form.address
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      address:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Contact d'urgence
                <input
                  value={
                    form.emergencyContact
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      emergencyContact:
                        event.target.value,
                    })
                  }
                />
              </label>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setShowEdit(false)
                }
              >
                Annuler
              </button>

              <button
                className="primary-action"
                type="submit"
              >
                Enregistrer
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
