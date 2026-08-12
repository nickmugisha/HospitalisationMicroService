export type AppointmentStatus =
  | "REQUESTED"
  | "SCHEDULED"
  | "CONFIRMED"
  | "CHECKED_IN"
  | "COMPLETED"
  | "REJECTED"
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

  createdBy:
    | "PATIENT"
    | "STAFF";

  createdAt: string;
  updatedAt: string;

  confirmedAt?: string;

  checkedInAt?: string;
  completedAt?: string;

  rejectedAt?: string;
  rejectionReason?: string;

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

export interface PatientAppointmentRequestInput {
  patientId: string;

  service: AppointmentService;

  preferredDate: string;
  preferredTime: string;

  reason: string;
  notes: string;
}
