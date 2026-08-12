import {
  Bell,
  CalendarCheck2,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  Edit3,
  LogIn,
  Plus,
  Printer,
  Search,
  UserRoundX,
  X,
  XCircle,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  approveAppointmentRequest,
  cancelAppointment,
  checkInAppointment,
  confirmAppointment,
  createAppointment,
  listAppointments,
  markNoShow,
  markReminderSent,
  rejectAppointmentRequest,
  updateAppointment,
} from "../services/appointmentService";

import {
  listPatients,
} from "../services/patientService";

import {
  exportAppointmentPdf,
  printAppointment,
} from "../services/documentService";

import type {
  Appointment,
  AppointmentService,
  CreateAppointmentInput,
} from "../types/appointment";

import type {
  Patient,
} from "../types/patient";

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

function pad(
  value: number
) {
  return String(value)
    .padStart(2, "0");
}

function localDateKey(
  date = new Date()
) {
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-");
}

function formatDate(
  value: string
) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      dateStyle: "medium",
    }
  ).format(
    new Date(
      `${value}T12:00:00`
    )
  );
}

function formatMonth(
  date: Date
) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      month: "long",
      year: "numeric",
    }
  ).format(date);
}

function statusLabel(
  status: Appointment["status"]
): string {
  switch (status) {
    case "REQUESTED":
      return "Demande en attente";

    case "SCHEDULED":
      return "Planifié";

    case "CONFIRMED":
      return "Confirmé";

    case "CHECKED_IN":
      return "Présent";

    case "COMPLETED":
      return "Terminé";

    case "REJECTED":
      return "Refusée";

    case "CANCELLED":
      return "Annulé";

    case "NO_SHOW":
      return "Absent";
  }
}

function initialForm(
  date: string,
  patientId = ""
): CreateAppointmentInput {
  return {
    patientId,

    service:
      "Consultation",

    doctorName:
      doctors[0],

    date,

    time:
      "08:00",

    durationMinutes:
      30,

    reason:
      "",

    notes:
      "",
  };
}

export default function AppointmentPage() {
  const today =
    localDateKey();

  const [appointments, setAppointments] =
    useState<Appointment[]>([]);

  const [patients, setPatients] =
    useState<Patient[]>([]);

  const [selectedDate, setSelectedDate] =
    useState(today);

  const [month, setMonth] =
    useState(
      new Date(
        `${today}T12:00:00`
      )
    );

  const [search, setSearch] =
    useState("");

  const [showForm, setShowForm] =
    useState(false);

  const [
    editingAppointment,
    setEditingAppointment,
  ] =
    useState<Appointment | null>(
      null
    );

  const [
    detailAppointment,
    setDetailAppointment,
  ] =
    useState<Appointment | null>(
      null
    );

  const [
    showCancellation,
    setShowCancellation,
  ] =
    useState(false);

  const [
    cancellationReason,
    setCancellationReason,
  ] =
    useState("");

  const [form, setForm] =
    useState<CreateAppointmentInput>(
      initialForm(today)
    );

  const [error, setError] =
    useState("");

  const [
    reviewDoctorName,
    setReviewDoctorName,
  ] = useState("");

  const [
    reviewDate,
    setReviewDate,
  ] = useState("");

  const [
    reviewTime,
    setReviewTime,
  ] = useState("");

  const [
    reviewDuration,
    setReviewDuration,
  ] = useState(30);

  const [
    requestRejectionReason,
    setRequestRejectionReason,
  ] = useState("");

  async function refresh() {
    const [
      appointmentData,
      patientData,
    ] = await Promise.all([
      listAppointments(),
      listPatients(),
    ]);

    setAppointments(
      appointmentData
    );

    setPatients(
      patientData
    );

    if (
      !form.patientId &&
      patientData.length > 0
    ) {
      setForm(
        current => ({
          ...current,
          patientId:
            patientData[0].id,
        })
      );
    }

    if (detailAppointment) {
      const fresh =
        appointmentData.find(
          item =>
            item.id ===
            detailAppointment.id
        );

      if (fresh) {
        setDetailAppointment(
          fresh
        );
      }
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (
      detailAppointment?.status !==
      "REQUESTED"
    ) {
      return;
    }

    setReviewDoctorName(
      detailAppointment.doctorName ||
        doctors[0]
    );

    setReviewDate(
      detailAppointment.date
    );

    setReviewTime(
      detailAppointment.time
    );

    setReviewDuration(
      detailAppointment.durationMinutes ||
        30
    );

    setRequestRejectionReason("");
  }, [
    detailAppointment,
  ]);

  const filteredAppointments =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return appointments;
      }

      return appointments.filter(
        appointment =>
          [
            appointment.patientName,
            appointment.patientNumber,
            appointment.appointmentNumber,
            appointment.doctorName,
            appointment.service,
            appointment.reason,
          ]
            .join(" ")
            .toLowerCase()
            .includes(value)
      );
    }, [
      appointments,
      search,
    ]);

  const pendingRequests =
    appointments
      .filter(
        appointment =>
          appointment.status ===
            "REQUESTED" &&
          appointment.createdBy ===
            "PATIENT"
      )
      .sort(
        (a, b) =>
          a.createdAt.localeCompare(
            b.createdAt
          )
      );

  const selectedAppointments =
    filteredAppointments
      .filter(
        appointment =>
          appointment.date ===
            selectedDate &&
          ![
            "REQUESTED",
            "REJECTED",
            "CANCELLED",
          ].includes(
            appointment.status
          )
      )
      .sort(
        (a, b) =>
          a.time.localeCompare(
            b.time
          )
      );

  const todayAppointments =
    appointments.filter(
      appointment =>
        appointment.date ===
          today &&
        ![
          "REQUESTED",
          "REJECTED",
          "CANCELLED",
        ].includes(
          appointment.status
        )
    );

  const confirmed =
    appointments.filter(
      appointment =>
        appointment.status ===
        "CONFIRMED"
    ).length;

  const checkedIn =
    appointments.filter(
      appointment =>
        appointment.status ===
        "CHECKED_IN"
    ).length;

  const upcoming =
    appointments.filter(
      appointment =>
        appointment.date >=
          today &&
        ![
          "REQUESTED",
          "COMPLETED",
          "REJECTED",
          "CANCELLED",
          "NO_SHOW",
        ].includes(
          appointment.status
        )
    ).length;

  const year =
    month.getFullYear();

  const monthIndex =
    month.getMonth();

  const daysInMonth =
    new Date(
      year,
      monthIndex + 1,
      0
    ).getDate();

  const firstDay =
    (
      new Date(
        year,
        monthIndex,
        1
      ).getDay() +
      6
    ) % 7;

  const calendarCells:
    Array<string | null> = [];

  for (
    let index = 0;
    index < firstDay;
    index++
  ) {
    calendarCells.push(null);
  }

  for (
    let day = 1;
    day <= daysInMonth;
    day++
  ) {
    calendarCells.push(
      `${year}-${pad(
        monthIndex + 1
      )}-${pad(day)}`
    );
  }

  function openCreate(
    date = selectedDate
  ) {
    setEditingAppointment(
      null
    );

    setError("");

    setForm(
      initialForm(
        date,
        patients[0]?.id ?? ""
      )
    );

    setShowForm(true);
  }

  function openEdit(
    appointment: Appointment
  ) {
    setEditingAppointment(
      appointment
    );

    setForm({
      patientId:
        appointment.patientId,

      service:
        appointment.service,

      doctorName:
        appointment.doctorName,

      date:
        appointment.date,

      time:
        appointment.time,

      durationMinutes:
        appointment.durationMinutes,

      reason:
        appointment.reason,

      notes:
        appointment.notes,
    });

    setError("");
    setShowForm(true);
  }

  async function handleSubmit(
    event:
      FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");

    try {
      if (
        editingAppointment
      ) {
        await updateAppointment(
          editingAppointment.id,
          form
        );
      } else {
        await createAppointment(
          form
        );
      }

      setShowForm(false);

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Impossible d'enregistrer le rendez-vous."
      );
    }
  }

  async function runAction(
    action:
      (
        id: string
      ) => Promise<Appointment>
  ) {
    if (!detailAppointment) {
      return;
    }

    setError("");

    try {
      const updated =
        await action(
          detailAppointment.id
        );

      setDetailAppointment(
        updated
      );

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Opération impossible."
      );
    }
  }

  async function handleCancel() {
    if (
      !detailAppointment ||
      !cancellationReason.trim()
    ) {
      setError(
        "Veuillez saisir le motif d'annulation."
      );

      return;
    }

    try {
      const updated =
        await cancelAppointment(
          detailAppointment.id,
          cancellationReason
        );

      setDetailAppointment(
        updated
      );

      setShowCancellation(
        false
      );

      setCancellationReason(
        ""
      );

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Annulation impossible."
      );
    }
  }

  async function handleApproveRequest() {
    if (
      !detailAppointment ||
      detailAppointment.status !==
        "REQUESTED"
    ) {
      return;
    }

    setError("");

    try {
      const updated =
        await approveAppointmentRequest(
          detailAppointment.id,
          reviewDoctorName,
          reviewDate,
          reviewTime,
          reviewDuration
        );

      setDetailAppointment(
        updated
      );

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Impossible de confirmer cette demande."
      );
    }
  }

  async function handleRejectRequest() {
    if (
      !detailAppointment ||
      detailAppointment.status !==
        "REQUESTED"
    ) {
      return;
    }

    if (
      !requestRejectionReason.trim()
    ) {
      setError(
        "Veuillez préciser la raison du refus."
      );

      return;
    }

    setError("");

    try {
      const updated =
        await rejectAppointmentRequest(
          detailAppointment.id,
          requestRejectionReason
        );

      setDetailAppointment(
        updated
      );

      setRequestRejectionReason("");

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Impossible de refuser cette demande."
      );
    }
  }

  function previousMonth() {
    setMonth(
      new Date(
        year,
        monthIndex - 1,
        1
      )
    );
  }

  function nextMonth() {
    setMonth(
      new Date(
        year,
        monthIndex + 1,
        1
      )
    );
  }

  return (
    <div className="appointment-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 08 • RENDEZ-VOUS
            & AGENDA
          </p>

          <h1>
            Rendez-vous & agenda
          </h1>

          <p className="subtitle">
            Planification médicale,
            disponibilité des médecins,
            check-in et suivi des rendez-vous.
          </p>
        </div>

        <button
          className="primary-action"
          onClick={() =>
            openCreate()
          }
        >
          <Plus size={18} />
          Nouveau rendez-vous
        </button>
      </header>

      <section className="dashboard-stats">
        <article>
          <div className="stat-icon">
            <Bell />
          </div>

          <div>
            <span>
              Demandes patients
            </span>

            <strong>
              {pendingRequests.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <CalendarDays />
          </div>

          <div>
            <span>
              Rendez-vous aujourd'hui
            </span>

            <strong>
              {todayAppointments.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Check />
          </div>

          <div>
            <span>
              Confirmés
            </span>

            <strong>
              {confirmed}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <LogIn />
          </div>

          <div>
            <span>
              Check-in effectué
            </span>

            <strong>
              {checkedIn}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Clock3 />
          </div>

          <div>
            <span>
              À venir
            </span>

            <strong>
              {upcoming}
            </strong>
          </div>
        </article>
      </section>

      <section className="appointment-request-panel">
        <div className="appointment-request-heading">
          <div>
            <span className="section-label">
              DEMANDES PATIENTS
            </span>

            <h2>
              Rendez-vous à valider
            </h2>

            <p>
              Les patients ont choisi
              un médecin et un créneau
              souhaités. Vérifiez leur
              disponibilité avant confirmation.
            </p>
          </div>

          <span className="appointment-request-count">
            {pendingRequests.length}
          </span>
        </div>

        <div className="appointment-request-list">
          {pendingRequests.map(
            appointment => (
              <article
                className="appointment-request-card"
                key={appointment.id}
              >
                <div className="appointment-request-avatar">
                  {appointment.patientName
                    .charAt(0)
                    .toUpperCase()}
                </div>

                <div className="appointment-request-info">
                  <span>
                    {
                      appointment.appointmentNumber
                    }
                  </span>

                  <h3>
                    {
                      appointment.patientName
                    }
                  </h3>

                  <p>
                    {
                      appointment.service
                    }
                    {" • "}
                    {
                      appointment.reason
                    }
                  </p>
                </div>

                <div className="appointment-request-preference">
                  <span>
                    MÉDECIN SOUHAITÉ
                  </span>

                  <strong>
                    {
                      appointment.doctorName ||
                      "Non précisé"
                    }
                  </strong>

                  <small>
                    {formatDate(
                      appointment.date
                    )}
                    {" • "}
                    {
                      appointment.time
                    }
                  </small>
                </div>

                <button
                  className="appointment-review-button"
                  onClick={() => {
                    setError("");

                    setDetailAppointment(
                      appointment
                    );
                  }}
                >
                  Examiner
                </button>
              </article>
            )
          )}

          {pendingRequests.length === 0 && (
            <div className="appointment-request-empty">
              <CheckCircle2 />

              <div>
                <strong>
                  Aucune demande en attente
                </strong>

                <span>
                  Toutes les demandes patient
                  ont été traitées.
                </span>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="appointment-workspace">
        <article className="calendar-card">
          <div className="calendar-header">
            <button
              onClick={
                previousMonth
              }
            >
              <ChevronLeft />
            </button>

            <div>
              <span className="section-label">
                CALENDRIER
              </span>

              <h2>
                {formatMonth(
                  month
                )}
              </h2>
            </div>

            <button
              onClick={
                nextMonth
              }
            >
              <ChevronRight />
            </button>
          </div>

          <div className="calendar-weekdays">
            <span>Lun</span>
            <span>Mar</span>
            <span>Mer</span>
            <span>Jeu</span>
            <span>Ven</span>
            <span>Sam</span>
            <span>Dim</span>
          </div>

          <div className="calendar-grid">
            {calendarCells.map(
              (
                date,
                index
              ) => {
                if (!date) {
                  return (
                    <div
                      className="calendar-cell empty"
                      key={`empty-${index}`}
                    />
                  );
                }

                const day =
                  Number(
                    date.slice(-2)
                  );

                const count =
                  appointments.filter(
                    appointment =>
                      appointment.date ===
                        date &&
                      appointment.status !==
                        "CANCELLED"
                  ).length;

                return (
                  <button
                    key={date}
                    className={[
                      "calendar-cell",
                      date ===
                        selectedDate
                        ? "selected"
                        : "",
                      date === today
                        ? "today"
                        : "",
                    ].join(" ")}
                    onClick={() =>
                      setSelectedDate(
                        date
                      )
                    }
                    onDoubleClick={() =>
                      openCreate(
                        date
                      )
                    }
                  >
                    <span>
                      {day}
                    </span>

                    {count > 0 && (
                      <strong>
                        {count}
                      </strong>
                    )}
                  </button>
                );
              }
            )}
          </div>

          <div className="calendar-hint">
            Double-cliquez sur une date
            pour créer un rendez-vous.
          </div>
        </article>

        <aside className="daily-agenda-card">
          <div className="daily-agenda-header">
            <div>
              <span className="section-label">
                AGENDA DU JOUR
              </span>

              <h2>
                {formatDate(
                  selectedDate
                )}
              </h2>
            </div>

            <span className="queue-count">
              {
                selectedAppointments.length
              }
            </span>
          </div>

          <div className="daily-agenda-list">
            {selectedAppointments.map(
              appointment => (
                <button
                  className="daily-appointment"
                  key={
                    appointment.id
                  }
                  onClick={() => {
                    setError("");

                    setDetailAppointment(
                      appointment
                    );
                  }}
                >
                  <div className="appointment-time">
                    {appointment.time}
                  </div>

                  <div>
                    <strong>
                      {
                        appointment.patientName
                      }
                    </strong>

                    <span>
                      {
                        appointment.service
                      }
                    </span>

                    <small>
                      {
                        appointment.doctorName
                      }
                    </small>
                  </div>

                  <span
                    className={`appointment-status ${appointment.status.toLowerCase()}`}
                  >
                    {statusLabel(
                      appointment.status
                    )}
                  </span>
                </button>
              )
            )}

            {selectedAppointments.length ===
              0 && (
              <div className="empty-queue">
                Aucun rendez-vous
                pour cette date.
              </div>
            )}
          </div>
        </aside>
      </section>

      <section className="appointment-register">
        <div className="panel-heading">
          <div>
            <span className="section-label">
              REGISTRE
            </span>

            <h2>
              Tous les rendez-vous
            </h2>
          </div>

          <div className="patient-search">
            <Search size={17} />

            <input
              value={search}
              onChange={event =>
                setSearch(
                  event.target.value
                )
              }
              placeholder="Patient, médecin, service..."
            />
          </div>
        </div>

        <div className="patient-table-wrapper">
          <table className="patient-table">
            <thead>
              <tr>
                <th>Rendez-vous</th>
                <th>Patient</th>
                <th>Date / heure</th>
                <th>Service</th>
                <th>Médecin</th>
                <th>Statut</th>
                <th>Rappel</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filteredAppointments.map(
                appointment => (
                  <tr
                    key={
                      appointment.id
                    }
                  >
                    <td>
                      <code>
                        {
                          appointment.appointmentNumber
                        }
                      </code>
                    </td>

                    <td>
                      <div className="patient-name">
                        <div className="patient-avatar">
                          {appointment.patientName
                            .charAt(0)
                            .toUpperCase()}
                        </div>

                        <div>
                          <strong>
                            {
                              appointment.patientName
                            }
                          </strong>

                          <span>
                            {
                              appointment.patientNumber
                            }
                          </span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <strong>
                        {formatDate(
                          appointment.date
                        )}
                      </strong>

                      <div className="appointment-table-time">
                        {
                          appointment.time
                        }
                        {" • "}
                        {
                          appointment.durationMinutes
                        }{" "}
                        min
                      </div>
                    </td>

                    <td>
                      {
                        appointment.service
                      }
                    </td>

                    <td>
                      {
                        appointment.doctorName
                      }
                    </td>

                    <td>
                      <span
                        className={`appointment-status ${appointment.status.toLowerCase()}`}
                      >
                        {statusLabel(
                          appointment.status
                        )}
                      </span>
                    </td>

                    <td>
                      {appointment.reminderSent
                        ? "Envoyé"
                        : "—"}
                    </td>

                    <td>
                      <button
                        className="table-action"
                        onClick={() => {
                          setError("");

                          setDetailAppointment(
                            appointment
                          );
                        }}
                      >
                        Ouvrir
                      </button>
                    </td>
                  </tr>
                )
              )}

              {filteredAppointments.length ===
                0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="empty-table"
                  >
                    Aucun rendez-vous.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {showForm && (
        <div className="modal-backdrop">
          <form
            className="patient-modal appointment-form-modal"
            onSubmit={
              handleSubmit
            }
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  {editingAppointment
                    ? "MODIFICATION"
                    : "PLANIFICATION"}
                </span>

                <h2>
                  {editingAppointment
                    ? "Modifier le rendez-vous"
                    : "Nouveau rendez-vous"}
                </h2>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setShowForm(
                    false
                  )
                }
              >
                <X size={20} />
              </button>
            </div>

            {error && (
              <div className="login-error">
                {error}
              </div>
            )}

            <div className="form-grid">
              <label>
                Patient *

                <select
                  value={
                    form.patientId
                  }
                  onChange={event =>
                    setForm({
                      ...form,
                      patientId:
                        event.target.value,
                    })
                  }
                  required
                >
                  <option value="">
                    Sélectionner...
                  </option>

                  {patients.map(
                    patient => (
                      <option
                        key={
                          patient.id
                        }
                        value={
                          patient.id
                        }
                      >
                        {
                          patient.firstName
                        }{" "}
                        {
                          patient.lastName
                        }
                        {" • "}
                        {
                          patient.patientNumber
                        }
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Service *

                <select
                  value={
                    form.service
                  }
                  onChange={event =>
                    setForm({
                      ...form,
                      service:
                        event.target
                          .value as AppointmentService,
                    })
                  }
                >
                  {services.map(
                    service => (
                      <option
                        key={
                          service
                        }
                      >
                        {service}
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Médecin *

                <select
                  value={
                    form.doctorName
                  }
                  onChange={event =>
                    setForm({
                      ...form,
                      doctorName:
                        event.target.value,
                    })
                  }
                >
                  {doctors.map(
                    doctor => (
                      <option
                        key={
                          doctor
                        }
                      >
                        {doctor}
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Date *

                <input
                  type="date"
                  min={today}
                  value={
                    form.date
                  }
                  onChange={event =>
                    setForm({
                      ...form,
                      date:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Heure *

                <input
                  type="time"
                  value={
                    form.time
                  }
                  onChange={event =>
                    setForm({
                      ...form,
                      time:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Durée

                <select
                  value={
                    form.durationMinutes
                  }
                  onChange={event =>
                    setForm({
                      ...form,
                      durationMinutes:
                        Number(
                          event.target.value
                        ),
                    })
                  }
                >
                  <option value={15}>
                    15 minutes
                  </option>

                  <option value={30}>
                    30 minutes
                  </option>

                  <option value={45}>
                    45 minutes
                  </option>

                  <option value={60}>
                    1 heure
                  </option>
                </select>
              </label>
            </div>

            <label className="modal-label">
              Motif *

              <textarea
                value={
                  form.reason
                }
                onChange={event =>
                  setForm({
                    ...form,
                    reason:
                      event.target.value,
                  })
                }
                placeholder="Motif du rendez-vous..."
                required
              />
            </label>

            <label className="modal-label">
              Notes

              <textarea
                value={
                  form.notes
                }
                onChange={event =>
                  setForm({
                    ...form,
                    notes:
                      event.target.value,
                  })
                }
                placeholder="Informations complémentaires..."
              />
            </label>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setShowForm(
                    false
                  )
                }
              >
                Annuler
              </button>

              <button
                className="primary-action"
                type="submit"
              >
                <CalendarCheck2
                  size={17}
                />

                {editingAppointment
                  ? "Enregistrer"
                  : "Planifier"}
              </button>
            </div>
          </form>
        </div>
      )}

      {detailAppointment && (
        <div className="modal-backdrop">
          <div className="appointment-detail-modal">
            <div className="modal-header">
              <div>
                <span className="section-label">
                  {
                    detailAppointment.appointmentNumber
                  }
                </span>

                <h2>
                  {
                    detailAppointment.patientName
                  }
                </h2>

                <p>
                  {
                    detailAppointment.patientNumber
                  }
                </p>
              </div>

              <button
                className="modal-close"
                onClick={() => {
                  setDetailAppointment(
                    null
                  );

                  setShowCancellation(
                    false
                  );

                  setError("");
                }}
              >
                <X size={20} />
              </button>
            </div>

            {error && (
              <div className="login-error">
                {error}
              </div>
            )}

            <div className="appointment-detail-status">
              <span
                className={`appointment-status ${detailAppointment.status.toLowerCase()}`}
              >
                {statusLabel(
                  detailAppointment.status
                )}
              </span>

              {detailAppointment.reminderSent && (
                <span className="reminder-done">
                  <Bell size={13} />
                  Rappel enregistré
                </span>
              )}
            </div>

            <div className="appointment-info-grid">
              <div>
                <span>Date</span>

                <strong>
                  {formatDate(
                    detailAppointment.date
                  )}
                </strong>
              </div>

              <div>
                <span>Heure</span>

                <strong>
                  {
                    detailAppointment.time
                  }
                </strong>
              </div>

              <div>
                <span>Durée</span>

                <strong>
                  {
                    detailAppointment.durationMinutes
                  }{" "}
                  min
                </strong>
              </div>

              <div>
                <span>Service</span>

                <strong>
                  {
                    detailAppointment.service
                  }
                </strong>
              </div>

              <div>
                <span>Médecin</span>

                <strong>
                  {
                    detailAppointment.doctorName
                  }
                </strong>
              </div>

              <div>
                <span>Motif</span>

                <strong>
                  {
                    detailAppointment.reason
                  }
                </strong>
              </div>
            </div>

            {detailAppointment.notes && (
              <div className="appointment-notes">
                {
                  detailAppointment.notes
                }
              </div>
            )}

            {detailAppointment.status ===
              "REQUESTED" && (
              <div className="appointment-request-review">
                <div className="appointment-request-review-title">
                  <div>
                    <span className="section-label">
                      DEMANDE DU PATIENT
                    </span>

                    <h3>
                      Vérifier et confirmer
                      le rendez-vous
                    </h3>
                  </div>

                  <span className="appointment-status requested">
                    En attente
                  </span>
                </div>

                <div className="appointment-request-original">
                  <span>
                    Le patient souhaite :
                  </span>

                  <strong>
                    {
                      detailAppointment.doctorName
                    }
                  </strong>

                  <small>
                    {formatDate(
                      detailAppointment.date
                    )}
                    {" à "}
                    {
                      detailAppointment.time
                    }
                  </small>
                </div>

                <div className="appointment-review-grid">
                  <label>
                    Médecin

                    <select
                      value={
                        reviewDoctorName
                      }
                      onChange={event =>
                        setReviewDoctorName(
                          event.target.value
                        )
                      }
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
                    Date définitive

                    <input
                      type="date"
                      min={today}
                      value={
                        reviewDate
                      }
                      onChange={event =>
                        setReviewDate(
                          event.target.value
                        )
                      }
                    />
                  </label>

                  <label>
                    Heure définitive

                    <input
                      type="time"
                      value={
                        reviewTime
                      }
                      onChange={event =>
                        setReviewTime(
                          event.target.value
                        )
                      }
                    />
                  </label>

                  <label>
                    Durée

                    <select
                      value={
                        reviewDuration
                      }
                      onChange={event =>
                        setReviewDuration(
                          Number(
                            event.target.value
                          )
                        )
                      }
                    >
                      <option value={15}>
                        15 minutes
                      </option>

                      <option value={30}>
                        30 minutes
                      </option>

                      <option value={45}>
                        45 minutes
                      </option>

                      <option value={60}>
                        1 heure
                      </option>
                    </select>
                  </label>
                </div>

                <button
                  className="appointment-approve-request"
                  onClick={
                    handleApproveRequest
                  }
                >
                  <CheckCircle2 size={17} />
                  Confirmer la demande
                </button>

                <div className="appointment-reject-request">
                  <label>
                    Si la demande doit être refusée

                    <textarea
                      value={
                        requestRejectionReason
                      }
                      onChange={event =>
                        setRequestRejectionReason(
                          event.target.value
                        )
                      }
                      placeholder="Ex. médecin indisponible, service indisponible..."
                    />
                  </label>

                  <button
                    onClick={
                      handleRejectRequest
                    }
                  >
                    <XCircle size={16} />
                    Refuser la demande
                  </button>
                </div>
              </div>
            )}

            {![
              "REQUESTED",
              "REJECTED",
            ].includes(
              detailAppointment.status
            ) && (
            <div className="appointment-document-actions">
              <button
                className="secondary-action billing-action-button"
                onClick={() =>
                  exportAppointmentPdf(
                    detailAppointment
                  )
                }
              >
                <Download size={16} />
                Ticket PDF
              </button>

              <button
                className="secondary-action billing-action-button"
                onClick={() =>
                  printAppointment(
                    detailAppointment
                  )
                }
              >
                <Printer size={16} />
                Imprimer
              </button>

              {[
                "SCHEDULED",
                "CONFIRMED",
              ].includes(
                detailAppointment.status
              ) && (
                <button
                  className="secondary-action billing-action-button"
                  onClick={() => {
                    openEdit(
                      detailAppointment
                    );

                    setDetailAppointment(
                      null
                    );
                  }}
                >
                  <Edit3 size={16} />
                  Modifier
                </button>
              )}
            </div>
            )}

            <div className="appointment-lifecycle-actions">
              {detailAppointment.status ===
                "SCHEDULED" && (
                <button
                  onClick={() =>
                    runAction(
                      confirmAppointment
                    )
                  }
                >
                  <Check size={17} />
                  Confirmer
                </button>
              )}

              {[
                "SCHEDULED",
                "CONFIRMED",
              ].includes(
                detailAppointment.status
              ) && (
                <button
                  onClick={() =>
                    runAction(
                      checkInAppointment
                    )
                  }
                >
                  <LogIn size={17} />
                  Check-in
                </button>
              )}


              {[
                "SCHEDULED",
                "CONFIRMED",
              ].includes(
                detailAppointment.status
              ) && (
                <button
                  onClick={() =>
                    runAction(
                      markNoShow
                    )
                  }
                >
                  <UserRoundX
                    size={17}
                  />
                  Absent
                </button>
              )}

              {!detailAppointment.reminderSent &&
                [
                  "SCHEDULED",
                  "CONFIRMED",
                ].includes(
                  detailAppointment.status
                ) && (
                <button
                  onClick={() =>
                    runAction(
                      markReminderSent
                    )
                  }
                >
                  <Bell size={17} />
                  Rappel envoyé
                </button>
              )}

              {![
                "REQUESTED",
                "REJECTED",
                "COMPLETED",
                "CANCELLED",
              ].includes(
                detailAppointment.status
              ) && (
                <button
                  className="danger"
                  onClick={() =>
                    setShowCancellation(
                      true
                    )
                  }
                >
                  <XCircle size={17} />
                  Annuler RDV
                </button>
              )}
            </div>

            {showCancellation && (
              <div className="appointment-cancel-box">
                <label>
                  Motif d'annulation

                  <textarea
                    value={
                      cancellationReason
                    }
                    onChange={event =>
                      setCancellationReason(
                        event.target.value
                      )
                    }
                    placeholder="Pourquoi ce rendez-vous est-il annulé ?"
                  />
                </label>

                <div>
                  <button
                    className="secondary-action"
                    onClick={() =>
                      setShowCancellation(
                        false
                      )
                    }
                  >
                    Retour
                  </button>

                  <button
                    className="appointment-cancel-confirm"
                    onClick={
                      handleCancel
                    }
                  >
                    Confirmer annulation
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
