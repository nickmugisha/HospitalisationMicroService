import {
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Clock3,
  HeartPulse,
  Plus,
} from "lucide-react";

import {
  useEffect,
  useState,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  useAuth,
} from "../auth/AuthContext";

import {
  listPatients,
} from "../services/patientService";

import {
  listPatientAppointments,
} from "../services/appointmentService";

import type {
  Appointment,
} from "../types/appointment";

export default function PatientDashboardPage() {
  const {
    user,
  } =
    useAuth();

  const navigate =
    useNavigate();

  const [
    appointments,
    setAppointments,
  ] =
    useState<Appointment[]>(
      []
    );

  const [
    patientFound,
    setPatientFound,
  ] =
    useState(true);

  useEffect(() => {
    async function load() {
      const patients =
        await listPatients();

      const patient =
        patients.find(
          current =>
            current.patientNumber ===
            user?.patientNumber
        );

      if (!patient) {
        setPatientFound(
          false
        );

        return;
      }

      setAppointments(
        await listPatientAppointments(
          patient.id
        )
      );
    }

    load();
  }, [
    user?.patientNumber,
  ]);

  if (!patientFound) {
    return (
      <div className="patient-empty-state">
        <HeartPulse />

        <h2>
          Dossier patient introuvable
        </h2>

        <p>
          Le compte connecté n'est
          associé à aucun dossier
          patient.
        </p>
      </div>
    );
  }

  const pending =
    appointments.filter(
      appointment =>
        appointment.status ===
        "REQUESTED"
    ).length;

  const confirmed =
    appointments.filter(
      appointment =>
        appointment.status ===
        "CONFIRMED"
    ).length;

  const completed =
    appointments.filter(
      appointment =>
        appointment.status ===
        "COMPLETED"
    ).length;

  const nextAppointment =
    appointments
      .filter(
        appointment =>
          appointment.status ===
            "CONFIRMED" &&
          appointment.date >=
            new Date()
              .toISOString()
              .slice(0, 10)
      )
      .sort(
        (a, b) =>
          `${a.date}T${a.time}`
            .localeCompare(
              `${b.date}T${b.time}`
            )
      )[0];

  return (
    <div className="patient-dashboard">
      <section className="patient-welcome-card">
        <div>
          <span>
            BIENVENUE
          </span>

          <h1>
            Bonjour,{" "}
            {user?.fullName}
          </h1>

          <p>
            Gérez vos rendez-vous
            et suivez votre parcours
            hospitalier depuis votre
            espace personnel.
          </p>
        </div>

        <button
          onClick={() =>
            navigate(
              "/patient/rendez-vous"
            )
          }
        >
          <Plus
            size={18}
          />

          Demander un rendez-vous
        </button>
      </section>

      <section className="patient-kpis">
        <article>
          <div>
            <Clock3 />
          </div>

          <span>
            Demandes en attente
          </span>

          <strong>
            {pending}
          </strong>
        </article>

        <article>
          <div>
            <CalendarClock />
          </div>

          <span>
            Rendez-vous confirmés
          </span>

          <strong>
            {confirmed}
          </strong>
        </article>

        <article>
          <div>
            <CheckCircle2 />
          </div>

          <span>
            Rendez-vous terminés
          </span>

          <strong>
            {completed}
          </strong>
        </article>
      </section>

      <section className="patient-next-card">
        <div className="patient-next-icon">
          <ClipboardList />
        </div>

        <div>
          <span>
            PROCHAIN RENDEZ-VOUS
          </span>

          {nextAppointment ? (
            <>
              <h2>
                {
                  nextAppointment.service
                }
              </h2>

              <p>
                {
                  nextAppointment.date
                }
                {" • "}
                {
                  nextAppointment.time
                }
                {" • "}
                {
                  nextAppointment.doctorName
                }
              </p>
            </>
          ) : (
            <>
              <h2>
                Aucun rendez-vous confirmé
              </h2>

              <p>
                Vous pouvez envoyer
                une nouvelle demande
                depuis votre espace.
              </p>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
