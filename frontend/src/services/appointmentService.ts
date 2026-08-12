import {
  getPatientById,
  registerArrival,
} from "./patientService";

import type {
  Appointment,
  AppointmentStatus,
  CreateAppointmentInput,
} from "../types/appointment";

const STORAGE_KEY =
  "hospitalis_appointments";

function loadAppointments():
  Appointment[] {
  const stored =
    localStorage.getItem(
      STORAGE_KEY
    );

  if (!stored) {
    return [];
  }

  try {
    const appointments =
      JSON.parse(
        stored
      ) as Appointment[];

    return appointments.map(
      (appointment) => ({
        ...appointment,

        createdBy:
          appointment.createdBy ??
          "STAFF",
      })
    );
  } catch {
    return [];
  }
}

function saveAppointments(
  appointments: Appointment[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(
      appointments
    )
  );
}

function generateAppointmentNumber(
  appointments: Appointment[]
) {
  const year =
    new Date().getFullYear();

  const max =
    appointments.reduce(
      (currentMax, appointment) => {
        const value =
          Number(
            appointment
              .appointmentNumber
              .split("-")
              .at(-1)
          );

        return Number.isNaN(value)
          ? currentMax
          : Math.max(
              currentMax,
              value
            );
      },
      0
    );

  return `RDV-${year}-${String(
    max + 1
  ).padStart(4, "0")}`;
}

function timeToMinutes(
  time: string
) {
  const [hours, minutes] =
    time.split(":").map(Number);

  return (
    (hours || 0) * 60 +
    (minutes || 0)
  );
}

function doctorHasConflict(
  appointments: Appointment[],
  input: {
    doctorName: string;
    date: string;
    time: string;
    durationMinutes: number;
  },
  ignoredAppointmentId?: string
) {
  const requestedStart =
    timeToMinutes(
      input.time
    );

  const requestedEnd =
    requestedStart +
    input.durationMinutes;

  return appointments.some(
    (appointment) => {
      if (
        appointment.id ===
          ignoredAppointmentId ||
        appointment.status ===
          "CANCELLED" ||
        appointment.status ===
          "NO_SHOW" ||
        appointment.doctorName
          .trim()
          .toLowerCase() !==
          input.doctorName
            .trim()
            .toLowerCase() ||
        appointment.date !==
          input.date
      ) {
        return false;
      }

      const existingStart =
        timeToMinutes(
          appointment.time
        );

      const existingEnd =
        existingStart +
        appointment.durationMinutes;

      return (
        requestedStart <
          existingEnd &&
        requestedEnd >
          existingStart
      );
    }
  );
}

export async function listAppointments():
  Promise<Appointment[]> {
  return loadAppointments()
    .sort(
      (a, b) =>
        `${a.date}T${a.time}`.localeCompare(
          `${b.date}T${b.time}`
        )
    );
}

export async function getAppointment(
  appointmentId: string
): Promise<Appointment | null> {
  return (
    loadAppointments().find(
      (appointment) =>
        appointment.id ===
        appointmentId
    ) ?? null
  );
}

export async function createAppointment(
  input: CreateAppointmentInput
): Promise<Appointment> {
  const patient =
    await getPatientById(
      input.patientId
    );

  if (!patient) {
    throw new Error(
      "Patient introuvable"
    );
  }

  if (!input.date) {
    throw new Error(
      "Date du rendez-vous obligatoire"
    );
  }

  if (!input.time) {
    throw new Error(
      "Heure du rendez-vous obligatoire"
    );
  }

  if (
    !input.doctorName.trim()
  ) {
    throw new Error(
      "Médecin obligatoire"
    );
  }

  if (
    !input.reason.trim()
  ) {
    throw new Error(
      "Motif obligatoire"
    );
  }

  if (
    !Number.isInteger(
      input.durationMinutes
    ) ||
    input.durationMinutes <= 0
  ) {
    throw new Error(
      "Durée du rendez-vous invalide"
    );
  }

  const appointments =
    loadAppointments();

  if (
    doctorHasConflict(
      appointments,
      {
        doctorName:
          input.doctorName,

        date:
          input.date,

        time:
          input.time,

        durationMinutes:
          input.durationMinutes,
      }
    )
  ) {
    throw new Error(
      "Ce médecin possède déjà un rendez-vous à cette date et cette heure"
    );
  }

  const now =
    new Date().toISOString();

  const appointment:
    Appointment = {
    id:
      crypto.randomUUID(),

    appointmentNumber:
      generateAppointmentNumber(
        appointments
      ),

    patientId:
      patient.id,

    patientNumber:
      patient.patientNumber,

    patientName:
      `${patient.firstName} ${patient.lastName}`,

    service:
      input.service,

    doctorName:
      input.doctorName.trim(),

    date:
      input.date,

    time:
      input.time,

    durationMinutes:
      input.durationMinutes,

    reason:
      input.reason.trim(),

    notes:
      input.notes.trim(),

    status:
      "SCHEDULED",

    reminderSent:
      false,

    createdBy:
      "STAFF",

    createdAt:
      now,

    updatedAt:
      now,
  };

  appointments.push(
    appointment
  );

  saveAppointments(
    appointments
  );

  return appointment;
}

export async function updateAppointment(
  appointmentId: string,
  input: CreateAppointmentInput
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      (appointment) =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  const patient =
    await getPatientById(
      input.patientId
    );

  if (!patient) {
    throw new Error(
      "Patient introuvable"
    );
  }

  if (
    doctorHasConflict(
      appointments,
      {
        doctorName:
          input.doctorName,

        date:
          input.date,

        time:
          input.time,

        durationMinutes:
          input.durationMinutes,
      },
      appointmentId
    )
  ) {
    throw new Error(
      "Ce médecin possède déjà un rendez-vous à cette date et cette heure"
    );
  }

  const current =
    appointments[index];

  appointments[index] = {
    ...current,

    patientId:
      patient.id,

    patientNumber:
      patient.patientNumber,

    patientName:
      `${patient.firstName} ${patient.lastName}`,

    service:
      input.service,

    doctorName:
      input.doctorName.trim(),

    date:
      input.date,

    time:
      input.time,

    durationMinutes:
      input.durationMinutes,

    reason:
      input.reason.trim(),

    notes:
      input.notes.trim(),

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

async function updateStatus(
  appointmentId: string,
  status: AppointmentStatus
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      (appointment) =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  appointments[index] = {
    ...appointments[index],

    status,

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function confirmAppointment(
  appointmentId: string
): Promise<Appointment> {
  const appointment =
    await getAppointment(
      appointmentId
    );

  if (!appointment) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  if (
    appointment.status !==
    "SCHEDULED"
  ) {
    throw new Error(
      "Seul un rendez-vous planifié peut être confirmé"
    );
  }

  return updateStatus(
    appointmentId,
    "CONFIRMED"
  );
}

export async function checkInAppointment(
  appointmentId: string
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      (appointment) =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  const appointment =
    appointments[index];

  if (
    appointment.status !==
      "SCHEDULED" &&
    appointment.status !==
      "CONFIRMED"
  ) {
    throw new Error(
      "Ce rendez-vous ne peut pas effectuer de check-in"
    );
  }

  await registerArrival(
    appointment.patientId,
    appointment.reason,
    appointment.service
  );

  appointments[index] = {
    ...appointment,

    status:
      "CHECKED_IN",

    checkedInAt:
      new Date().toISOString(),

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function completeAppointment(
  appointmentId: string
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      (appointment) =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  if (
    appointments[index]
      .status === "CANCELLED"
  ) {
    throw new Error(
      "Un rendez-vous annulé ne peut pas être terminé"
    );
  }

  appointments[index] = {
    ...appointments[index],

    status:
      "COMPLETED",

    completedAt:
      new Date().toISOString(),

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function cancelAppointment(
  appointmentId: string,
  reason: string
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      (appointment) =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  if (
    appointments[index]
      .status === "COMPLETED"
  ) {
    throw new Error(
      "Un rendez-vous terminé ne peut pas être annulé"
    );
  }

  appointments[index] = {
    ...appointments[index],

    status:
      "CANCELLED",

    cancellationReason:
      reason.trim(),

    cancelledAt:
      new Date().toISOString(),

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function markNoShow(
  appointmentId: string
): Promise<Appointment> {
  const appointment =
    await getAppointment(
      appointmentId
    );

  if (!appointment) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  if (
    appointment.status ===
      "COMPLETED" ||
    appointment.status ===
      "CANCELLED"
  ) {
    throw new Error(
      "Ce rendez-vous ne peut pas être marqué absent"
    );
  }

  return updateStatus(
    appointmentId,
    "NO_SHOW"
  );
}

export async function markReminderSent(
  appointmentId: string
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      (appointment) =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Rendez-vous introuvable"
    );
  }

  appointments[index] = {
    ...appointments[index],

    reminderSent:
      true,

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function getAppointmentsByDate(
  date: string
): Promise<Appointment[]> {
  return (
    await listAppointments()
  ).filter(
    (appointment) =>
      appointment.date ===
      date
  );
}

export async function getTodayAppointments():
  Promise<Appointment[]> {
  const today =
    new Date()
      .toISOString()
      .slice(0, 10);

  return getAppointmentsByDate(
    today
  );
}

export async function getUpcomingAppointments(
  days = 7
): Promise<Appointment[]> {
  const appointments =
    await listAppointments();

  const start =
    new Date();

  start.setHours(
    0,
    0,
    0,
    0
  );

  const end =
    new Date(start);

  end.setDate(
    end.getDate() +
      days
  );

  return appointments.filter(
    (appointment) => {
      if (
        appointment.status ===
          "CANCELLED" ||
        appointment.status ===
          "COMPLETED" ||
        appointment.status ===
          "NO_SHOW"
      ) {
        return false;
      }

      const date =
        new Date(
          `${appointment.date}T${appointment.time}:00`
        );

      return (
        date >= start &&
        date <= end
      );
    }
  );
}

export async function requestAppointmentByPatient(
  input: {
    patientId: string;
    service: Appointment["service"];
    preferredDoctorName: string;
    preferredDate: string;
    preferredTime: string;
    reason: string;
    notes: string;
  }
): Promise<Appointment> {
  const patient =
    await getPatientById(
      input.patientId
    );

  if (!patient) {
    throw new Error(
      "Patient introuvable"
    );
  }

  if (!input.preferredDate) {
    throw new Error(
      "Veuillez choisir une date."
    );
  }

  if (!input.preferredTime) {
    throw new Error(
      "Veuillez choisir une heure."
    );
  }

  if (!input.preferredDoctorName.trim()) {
    throw new Error(
      "Veuillez choisir un médecin."
    );
  }

  if (!input.reason.trim()) {
    throw new Error(
      "Veuillez préciser le motif du rendez-vous."
    );
  }

  const appointments =
    loadAppointments();

  const now =
    new Date().toISOString();

  const appointment: Appointment = {
    id:
      crypto.randomUUID(),

    appointmentNumber:
      generateAppointmentNumber(
        appointments
      ),

    patientId:
      patient.id,

    patientNumber:
      patient.patientNumber,

    patientName:
      `${patient.firstName} ${patient.lastName}`,

    service:
      input.service,

    doctorName:
      input.preferredDoctorName.trim(),

    date:
      input.preferredDate,

    time:
      input.preferredTime,

    durationMinutes:
      30,

    reason:
      input.reason.trim(),

    notes:
      input.notes.trim(),

    status:
      "REQUESTED",

    reminderSent:
      false,

    createdBy:
      "PATIENT",

    createdAt:
      now,

    updatedAt:
      now,
  };

  appointments.push(
    appointment
  );

  saveAppointments(
    appointments
  );

  return appointment;
}

export async function approveAppointmentRequest(
  appointmentId: string,
  doctorName: string,
  date: string,
  time: string,
  durationMinutes = 30
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      appointment =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Demande introuvable"
    );
  }

  const current =
    appointments[index];

  if (
    current.status !==
    "REQUESTED"
  ) {
    throw new Error(
      "Cette demande a déjà été traitée."
    );
  }

  if (!doctorName.trim()) {
    throw new Error(
      "Veuillez attribuer un médecin."
    );
  }

  if (
    doctorHasConflict(
      appointments,
      {
        doctorName,
        date,
        time,
        durationMinutes,
      },
      appointmentId
    )
  ) {
    throw new Error(
      "Ce médecin est déjà occupé sur ce créneau."
    );
  }

  appointments[index] = {
    ...current,

    doctorName:
      doctorName.trim(),

    date,

    time,

    durationMinutes,

    status:
      "CONFIRMED",

    confirmedAt:
      new Date().toISOString(),

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function rejectAppointmentRequest(
  appointmentId: string,
  reason: string
): Promise<Appointment> {
  const appointments =
    loadAppointments();

  const index =
    appointments.findIndex(
      appointment =>
        appointment.id ===
        appointmentId
    );

  if (index === -1) {
    throw new Error(
      "Demande introuvable"
    );
  }

  if (
    appointments[index].status !==
    "REQUESTED"
  ) {
    throw new Error(
      "Cette demande a déjà été traitée."
    );
  }

  if (!reason.trim()) {
    throw new Error(
      "Veuillez préciser la raison du refus."
    );
  }

  appointments[index] = {
    ...appointments[index],

    status:
      "REJECTED",

    rejectionReason:
      reason.trim(),

    rejectedAt:
      new Date().toISOString(),

    updatedAt:
      new Date().toISOString(),
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}

export async function listPatientAppointments(
  patientId: string
): Promise<Appointment[]> {
  return (
    await listAppointments()
  ).filter(
    appointment =>
      appointment.patientId ===
      patientId
  );
}

export async function completePatientAppointmentForService(
  patientId: string,
  service: Appointment["service"]
): Promise<Appointment | null> {
  const appointments =
    loadAppointments();

  const candidates =
    appointments
      .filter(
        appointment =>
          appointment.patientId ===
            patientId &&
          appointment.service ===
            service &&
          appointment.status ===
            "CHECKED_IN"
      )
      .sort(
        (a, b) => {
          const dateA =
            a.checkedInAt ??
            a.updatedAt ??
            a.createdAt;

          const dateB =
            b.checkedInAt ??
            b.updatedAt ??
            b.createdAt;

          return (
            new Date(dateB).getTime() -
            new Date(dateA).getTime()
          );
        }
      );

  const appointment =
    candidates[0];

  if (!appointment) {
    return null;
  }

  const index =
    appointments.findIndex(
      current =>
        current.id ===
        appointment.id
    );

  if (index === -1) {
    return null;
  }

  const now =
    new Date().toISOString();

  appointments[index] = {
    ...appointments[index],

    status:
      "COMPLETED",

    completedAt:
      now,

    updatedAt:
      now,
  };

  saveAppointments(
    appointments
  );

  return appointments[index];
}
