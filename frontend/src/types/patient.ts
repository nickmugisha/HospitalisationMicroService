export type PatientSex = "M" | "F";

export type PatientStatus =
  | "ACTIVE"
  | "INACTIVE"
  | "DECEASED";

export type ArrivalStatus =
  | "NONE"
  | "WAITING"
  | "ORIENTED";

export type PatientHistoryType =
  | "CREATED"
  | "CHECK_IN"
  | "ORIENTED"
  | "TRANSFER"
  | "UPDATED";

export interface PatientHistoryEntry {
  id: string;
  type: PatientHistoryType;
  label: string;
  note?: string;
  service?: string;
  at: string;
}

export interface Patient {
  id: string;
  patientNumber: string;

  firstName: string;
  lastName: string;

  sex: PatientSex;
  birthDate: string;

  phone: string;
  email?: string;
  address: string;

  emergencyContact: string;

  status: PatientStatus;
  arrivalStatus: ArrivalStatus;

  arrivalReason?: string;
  targetService?: string;

  history?: PatientHistoryEntry[];

  createdAt: string;
  updatedAt?: string;
}

export interface CreatePatientInput {
  firstName: string;
  lastName: string;

  sex: PatientSex;
  birthDate: string;

  phone: string;
  email?: string;
  address: string;

  emergencyContact: string;
}
