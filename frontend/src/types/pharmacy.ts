export type StockMovementType =
  | "RECEIVE"
  | "DISPENSE"
  | "ADJUSTMENT";

export type PharmacyOrderStatus =
  | "WAITING"
  | "PARTIAL"
  | "DISPENSED";

export interface Medication {
  id: string;

  name: string;
  genericName: string;

  form: string;
  strength: string;
  unit: string;

  salePrice: number;
  reorderLevel: number;

  active: boolean;
}

export interface StockBatch {
  id: string;

  medicationId: string;

  batchNumber: string;
  expiryDate: string;

  quantity: number;

  receivedAt: string;
}

export interface StockMovement {
  id: string;

  medicationId: string;
  batchId?: string;

  type: StockMovementType;

  quantity: number;

  reference: string;
  note?: string;

  createdAt: string;
}

export interface PharmacyOrderItem {
  id: string;

  prescriptionItemId: string;

  prescribedName: string;

  dosage: string;
  frequency: string;
  duration: string;

  medicationId?: string;

  requestedQuantity: number;
  dispensedQuantity: number;
}

export interface PharmacyOrder {
  id: string;

  consultationId: string;

  patientId: string;
  patientNumber: string;
  patientName: string;

  status: PharmacyOrderStatus;

  items: PharmacyOrderItem[];

  createdAt: string;
  dispensedAt?: string;
}
