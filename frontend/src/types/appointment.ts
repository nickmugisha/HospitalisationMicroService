export type AppointmentStatus =
  | "SCHEDULED"
  | "CONFIRMED"
  | "CHECKED_IN"
  | "COMPLETED"
  | "CANCELLED"
  | "NO_SHOW";

export type AppointmentService =
  | "Consultation"
  | "Laboratoire"
  | "Hospitalisation"
  | "Maternité"
  | "Pharmacie"
  | "Imagerie"
  | "Urgences";

export interface Appointment {
  id: string;

  appointmentNumber: string;

  patientId: string;
  patientNumber: string;
  patientName: string;

  service: AppointmentService;

  doctorName: string;

  date: string;
  time: string;

  durationMinutes: number;

  reason: string;
  notes: string;

  status: AppointmentStatus;

  reminderSent: boolean;

  createdAt: string;
  updatedAt: string;

  confirmedAt?: string;
  checkedInAt?: string;
  completedAt?: string;

  cancelledAt?: string;
  cancellationReason?: string;
}

export interface CreateAppointmentInput {
  patientId: string;

  service: AppointmentService;

  doctorName: string;

  date: string;
  time: string;

  durationMinutes: number;

  reason: string;
  notes: string;
}
