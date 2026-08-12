export type InvoiceStatus =
  | "OPEN"
  | "PARTIAL"
  | "PAID";

export type BillingSource =
  | "CONSULTATION"
  | "LABORATORY"
  | "HOSPITALIZATION"
  | "PHARMACY"
  | "MATERNITY"
  | "OTHER";

export type PaymentMethod =
  | "CASH"
  | "MOBILE_MONEY"
  | "BANK"
  | "CARD";

export interface InvoiceItem {
  id: string;

  sourceType: BillingSource;
  sourceId: string;

  description: string;

  quantity: number;
  unitPrice: number;
  total: number;

  createdAt: string;
}

export interface InvoicePayment {
  id: string;

  amount: number;
  method: PaymentMethod;

  reference?: string;

  paidAt: string;
}

export interface Invoice {
  id: string;
  invoiceNumber: string;

  patientId: string;
  patientNumber: string;
  patientName: string;

  status: InvoiceStatus;

  items: InvoiceItem[];
  payments: InvoicePayment[];

  createdAt: string;
  updatedAt: string;
}
