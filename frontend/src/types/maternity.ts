export type MaternityStatus =
  | "WAITING"
  | "ADMITTED"
  | "IN_LABOR"
  | "DELIVERED"
  | "DISCHARGED";

export type DeliveryType =
  | "VAGINAL"
  | "CESAREAN"
  | "ASSISTED";

export type NewbornSex =
  | "M"
  | "F";

export interface Newborn {
  id: string;

  name: string;
  sex: NewbornSex;

  weightGrams: number;
  lengthCm: number;

  apgar1: number;
  apgar5: number;

  observations: string;

  bornAt: string;
}

export interface MaternityCase {
  id: string;

  patientId: string;
  patientNumber: string;
  patientName: string;

  reason: string;

  status: MaternityStatus;

  gestationalAgeWeeks: string;
  gravida: string;
  para: string;

  bloodGroup: string;
  estimatedDueDate: string;

  riskNotes: string;

  admissionNotes: string;

  deliveryType?: DeliveryType;
  deliveryNotes?: string;

  newborn?: Newborn;

  dischargeNotes?: string;

  requestedAt: string;
  admittedAt?: string;
  laborStartedAt?: string;
  deliveredAt?: string;
  dischargedAt?: string;
}
