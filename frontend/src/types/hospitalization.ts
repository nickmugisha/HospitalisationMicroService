export type HospitalizationStatus =
  | "WAITING"
  | "ADMITTED"
  | "DISCHARGED";

export interface HospitalBed {
  id: string;
  ward: string;
  roomNumber: string;
  bedNumber: string;
  occupiedByAdmissionId?: string;
}

export interface HospitalizationAdmission {
  id: string;

  consultationId: string;

  patientId: string;
  patientNumber: string;
  patientName: string;

  reason: string;

  status: HospitalizationStatus;

  requestedAt: string;

  bedId?: string;
  ward?: string;
  roomNumber?: string;
  bedNumber?: string;

  admissionNotes?: string;
  dischargeNotes?: string;

  admittedAt?: string;
  dischargedAt?: string;
}
