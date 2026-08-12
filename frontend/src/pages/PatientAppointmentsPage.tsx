import {
  CalendarCheck2,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Plus,
  Send,
  X,
  XCircle,
} from "lucide-react";

import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import {
  useAuth,
} from "../auth/AuthContext";

import {
  listPatients,
} from "../services/patientService";

import {
  cancelAppointment,
  listPatientAppointments,
  requestAppointmentByPatient,
} from "../services/appointmentService";

import type {
  Appointment,
  AppointmentService,
} from "../types/appointment";

const services:
  AppointmentService[] = [
  "Consultation",
  "Laboratoire",
  "Hospitalisation",
  "Maternité",
  "Pharmacie",
];

const doctors = [
  "Dr Jean Niyonzima",
  "Dr Diane Ndayisenga",
  "Dr Patrick Nkurunziza",
  "Dr Aline Irakoze",
  "Dr Eric Nahimana",
];

function localDateKey() {
  const date =
    new Date();

  const year =
    date.getFullYear();

  const month =
    String(
      date.getMonth() + 1
    ).padStart(
      2,
      "0"
    );

  const day =
    String(
      date.getDate()
    ).padStart(
      2,
      "0"
    );

  return `${year}-${month}-${day}`;
}

function statusLabel(
  appointment:
    Appointment
) {
  switch (
    appointment.status
  ) {
    case "REQUESTED":
      return "En attente de validation";

    case "SCHEDULED":
      return "Planifié";

    case "CONFIRMED":
      return "Confirmé";

    case "CHECKED_IN":
      return "Présent";

    case "COMPLETED":
      return "Terminé";

    case "REJECTED":
      return "Refusé";

    case "CANCELLED":
      return "Annulé";

    case "NO_SHOW":
      return "Absent";
  }
}

export default function PatientAppointmentsPage() {
  const {
    user,
  } =
    useAuth();

  const [
    patientId,
    setPatientId,
  ] =
    useState("");

  const [
    appointments,
    setAppointments,
  ] =
    useState<Appointment[]>(
      []
    );

  const [
    showRequest,
    setShowRequest,
  ] =
    useState(false);

  const [
    service,
    setService,
  ] =
    useState<AppointmentService>(
      "Consultation"
    );

  const [
    doctorName,
    setDoctorName,
  ] =
    useState(
      doctors[0]
    );

  const [
    date,
    setDate,
  ] =
    useState("");

  const [
    time,
    setTime,
  ] =
    useState("");

  const [
    reason,
    setReason,
  ] =
    useState("");

  const [
    notes,
    setNotes,
  ] =
    useState("");

  const [
    error,
    setError,
  ] =
    useState("");

  const [
    success,
    setSuccess,
  ] =
    useState("");

  async function refresh(
    forcedPatientId?:
      string
  ) {
    const id =
      forcedPatientId ??
      patientId;

    if (!id) {
      return;
    }

    setAppointments(
      await listPatientAppointments(
        id
      )
    );
  }

  useEffect(() => {
    async function initialize() {
      const patients =
        await listPatients();

      const patient =
        patients.find(
          current =>
            current.patientNumber ===
            user?.patientNumber
        );

      if (!patient) {
        setError(
          "Votre compte n'est pas associé à un dossier patient."
        );

        return;
      }

      setPatientId(
        patient.id
      );

      await refresh(
        patient.id
      );
    }

    initialize();
  }, [
    user?.patientNumber,
  ]);

  async function handleRequest(
    event:
      FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!patientId) {
      setError(
        "Dossier patient introuvable."
      );

      return;
    }

    try {
      const appointment =
        await requestAppointmentByPatient({
          patientId,

          service,

          preferredDoctorName:
            doctorName,

          preferredDate:
            date,

          preferredTime:
            time,

          reason,

          notes,
        });

      setSuccess(
        `Votre demande ${appointment.appointmentNumber} a été envoyée à l'hôpital.`
      );

      setShowRequest(
        false
      );

      setDate("");
      setTime("");
      setReason("");
      setNotes("");

      await refresh(
        patientId
      );
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Impossible d'envoyer la demande."
      );
    }
  }

  async function handleCancel(
    appointment:
      Appointment
  ) {
    const reason =
      window.prompt(
        "Pourquoi souhaitez-vous annuler ce rendez-vous ?"
      );

    if (
      !reason?.trim()
    ) {
      return;
    }

    try {
      await cancelAppointment(
        appointment.id,
        reason
      );

      await refresh(
        patientId
      );
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Annulation impossible."
      );
    }
  }

  return (
    <div className="patient-appointments-page">
      <header className="patient-page-header">
        <div>
          <span>
            MES RENDEZ-VOUS
          </span>

          <h1>
            Rendez-vous médicaux
          </h1>

          <p>
            Envoyez une demande et
            suivez sa validation par
            l'établissement.
          </p>
        </div>

        <button
          onClick={() => {
            setError("");
            setSuccess("");

            setShowRequest(
              true
            );
          }}
        >
          <Plus
            size={18}
          />

          Demander un rendez-vous
        </button>
      </header>

      {error && (
        <div className="patient-message error">
          {error}
        </div>
      )}

      {success && (
        <div className="patient-message success">
          <CheckCircle2
            size={17}
          />

          {success}
        </div>
      )}

      <section className="patient-appointment-list">
        {appointments.map(
          appointment => (
            <article
              key={
                appointment.id
              }
              className="patient-appointment-card"
            >
              <div className="patient-appointment-date">
                <CalendarDays />

                <strong>
                  {
                    appointment.date
                  }
                </strong>

                <span>
                  {
                    appointment.time
                  }
                </span>
              </div>

              <div className="patient-appointment-information">
                <span>
                  {
                    appointment.appointmentNumber
                  }
                </span>

                <h2>
                  {
                    appointment.service
                  }
                </h2>

                <p>
                  {
                    appointment.reason
                  }
                </p>

                {appointment.doctorName ? (
                  <small>
                    {appointment.status ===
                    "REQUESTED"
                      ? "Médecin souhaité : "
                      : "Médecin : "}

                    {
                      appointment.doctorName
                    }
                  </small>
                ) : (
                  <small>
                    Aucun médecin sélectionné
                  </small>
                )}
              </div>

              <div className="patient-appointment-state">
                <span
                  className={`appointment-status ${appointment.status.toLowerCase()}`}
                >
                  {statusLabel(
                    appointment
                  )}
                </span>

                {appointment.status ===
                  "REJECTED" &&
                  appointment.rejectionReason && (
                  <small className="patient-rejection-reason">
                    {
                      appointment.rejectionReason
                    }
                  </small>
                )}

                {[
                  "REQUESTED",
                  "SCHEDULED",
                  "CONFIRMED",
                ].includes(
                  appointment.status
                ) && (
                  <button
                    onClick={() =>
                      handleCancel(
                        appointment
                      )
                    }
                  >
                    <XCircle
                      size={15}
                    />

                    Annuler
                  </button>
                )}
              </div>
            </article>
          )
        )}

        {appointments.length ===
          0 && (
          <div className="patient-empty-state">
            <CalendarCheck2 />

            <h2>
              Aucun rendez-vous
            </h2>

            <p>
              Vous n'avez encore
              envoyé aucune demande.
            </p>
          </div>
        )}
      </section>

      {showRequest && (
        <div className="modal-backdrop">
          <form
            className="patient-modal patient-request-modal"
            onSubmit={
              handleRequest
            }
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  DEMANDE PATIENT
                </span>

                <h2>
                  Demander un rendez-vous
                </h2>

                <p>
                  Choisissez le service
                  et votre créneau
                  souhaité.
                </p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setShowRequest(
                    false
                  )
                }
              >
                <X
                  size={20}
                />
              </button>
            </div>

            <div className="patient-request-identity">
              <strong>
                {
                  user?.fullName
                }
              </strong>

              <span>
                {
                  user?.patientNumber
                }
              </span>
            </div>

            <div className="form-grid">
              <label>
                Service demandé *

                <select
                  value={
                    service
                  }
                  onChange={event =>
                    setService(
                      event.target
                        .value as AppointmentService
                    )
                  }
                >
                  {services.map(
                    current => (
                      <option
                        key={
                          current
                        }
                      >
                        {
                          current
                        }
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Médecin souhaité *

                <select
                  value={
                    doctorName
                  }
                  onChange={event =>
                    setDoctorName(
                      event.target.value
                    )
                  }
                  required
                >
                  {doctors.map(
                    doctor => (
                      <option
                        key={doctor}
                        value={doctor}
                      >
                        {doctor}
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Date souhaitée *

                <input
                  type="date"
                  min={
                    localDateKey()
                  }
                  value={
                    date
                  }
                  onChange={event =>
                    setDate(
                      event.target.value
                    )
                  }
                  required
                />
              </label>

              <label>
                Heure souhaitée *

                <input
                  type="time"
                  value={
                    time
                  }
                  onChange={event =>
                    setTime(
                      event.target.value
                    )
                  }
                  required
                />
              </label>
            </div>

            <label className="modal-label">
              Motif du rendez-vous *

              <textarea
                value={
                  reason
                }
                onChange={event =>
                  setReason(
                    event.target.value
                  )
                }
                placeholder="Expliquez brièvement pourquoi vous souhaitez consulter..."
                required
              />
            </label>

            <label className="modal-label">
              Informations complémentaires

              <textarea
                value={
                  notes
                }
                onChange={event =>
                  setNotes(
                    event.target.value
                  )
                }
                placeholder="Informations supplémentaires si nécessaire..."
              />
            </label>

            <div className="patient-request-notice">
              <Clock3
                size={17}
              />

              <span>
                Le médecin et le
                créneau sélectionnés
                représentent votre
                demande. L'hôpital
                vérifiera leur
                disponibilité avant
                confirmation.
              </span>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setShowRequest(
                    false
                  )
                }
              >
                Annuler
              </button>

              <button
                type="submit"
                className="primary-action"
              >
                <Send
                  size={17}
                />

                Envoyer ma demande
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
