export type ConsultationStatus =
  | "WAITING"
  | "IN_PROGRESS"
  | "COMPLETED";

export interface VitalSigns {
  temperature: string;
  bloodPressure: string;
  heartRate: string;
  weight: string;
  height: string;
  oxygenSaturation: string;
}

export interface PrescriptionItem {
  id: string;
  medicine: string;
  dosage: string;
  frequency: string;
  duration: string;
}

export interface Consultation {
  id: string;
  patientId: string;
  patientNumber: string;
  patientName: string;

  status: ConsultationStatus;

  reason: string;

  symptoms: string;
  diagnosis: string;
  clinicalNotes: string;

  vitalSigns: VitalSigns;

  prescriptions: PrescriptionItem[];

  laboratoryRequested: boolean;
  laboratoryNotes?: string;

  hospitalizationRequested: boolean;
  hospitalizationReason?: string;

  startedAt?: string;
  completedAt?: string;
  createdAt: string;
}
