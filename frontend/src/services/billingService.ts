import {
  listConsultations,
} from "./consultationService";

import {
  listLaboratoryRequests,
} from "./laboratoryService";

import {
  listAdmissions,
} from "./hospitalizationService";

import type {
  BillingSource,
  Invoice,
  InvoiceItem,
  InvoicePayment,
  PaymentMethod,
} from "../types/billing";

const STORAGE_KEY =
  "hospitalis_invoices";

const TARIFFS = {
  CONSULTATION: 20000,
  LABORATORY: 15000,
  HOSPITALIZATION: 50000,
};

function loadInvoices(): Invoice[] {
  const stored =
    localStorage.getItem(
      STORAGE_KEY
    );

  if (!stored) {
    return [];
  }

  try {
    return JSON.parse(
      stored
    ) as Invoice[];
  } catch {
    return [];
  }
}

function saveInvoices(
  invoices: Invoice[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(invoices)
  );
}

function generateInvoiceNumber(
  invoices: Invoice[]
) {
  const year =
    new Date().getFullYear();

  const max =
    invoices.reduce(
      (currentMax, invoice) => {
        const last =
          Number(
            invoice.invoiceNumber
              .split("-")
              .at(-1)
          );

        return Number.isNaN(last)
          ? currentMax
          : Math.max(
              currentMax,
              last
            );
      },
      0
    );

  return `FAC-${year}-${String(
    max + 1
  ).padStart(4, "0")}`;
}

export function invoiceTotal(
  invoice: Invoice
) {
  return invoice.items.reduce(
    (total, item) =>
      total + item.total,
    0
  );
}

export function invoicePaid(
  invoice: Invoice
) {
  return invoice.payments.reduce(
    (total, payment) =>
      total + payment.amount,
    0
  );
}

export function invoiceBalance(
  invoice: Invoice
) {
  return Math.max(
    invoiceTotal(invoice) -
      invoicePaid(invoice),
    0
  );
}

function calculateStatus(
  invoice: Invoice
): Invoice["status"] {
  const total =
    invoiceTotal(invoice);

  const paid =
    invoicePaid(invoice);

  if (
    total > 0 &&
    paid >= total
  ) {
    return "PAID";
  }

  if (paid > 0) {
    return "PARTIAL";
  }

  return "OPEN";
}

function sourceAlreadyBilled(
  invoices: Invoice[],
  sourceType: BillingSource,
  sourceId: string
) {
  return invoices.some(
    (invoice) =>
      invoice.items.some(
        (item) =>
          item.sourceType ===
            sourceType &&
          item.sourceId ===
            sourceId
      )
  );
}

function findOrCreateOpenInvoice(
  invoices: Invoice[],
  patient: {
    id: string;
    number: string;
    name: string;
  }
): Invoice {
  const existing =
    invoices.find(
      (invoice) =>
        invoice.patientId ===
          patient.id &&
        invoice.status !== "PAID"
    );

  if (existing) {
    return existing;
  }

  const now =
    new Date().toISOString();

  const invoice: Invoice = {
    id: crypto.randomUUID(),

    invoiceNumber:
      generateInvoiceNumber(
        invoices
      ),

    patientId:
      patient.id,

    patientNumber:
      patient.number,

    patientName:
      patient.name,

    status: "OPEN",

    items: [],
    payments: [],

    createdAt: now,
    updatedAt: now,
  };

  invoices.unshift(invoice);

  return invoice;
}

function addItem(
  invoice: Invoice,
  input: {
    sourceType: BillingSource;
    sourceId: string;
    description: string;
    amount: number;
  }
) {
  const item: InvoiceItem = {
    id: crypto.randomUUID(),

    sourceType:
      input.sourceType,

    sourceId:
      input.sourceId,

    description:
      input.description,

    quantity: 1,

    unitPrice:
      input.amount,

    total:
      input.amount,

    createdAt:
      new Date().toISOString(),
  };

  invoice.items.push(item);

  invoice.updatedAt =
    new Date().toISOString();

  invoice.status =
    calculateStatus(invoice);
}

export async function synchronizeBilling():
  Promise<Invoice[]> {
  const invoices =
    loadInvoices();

  const consultations =
    await listConsultations();

  const laboratoryRequests =
    await listLaboratoryRequests();

  const admissions =
    await listAdmissions();

  for (
    const consultation
    of consultations
  ) {
    if (
      consultation.status ===
      "WAITING"
    ) {
      continue;
    }

    if (
      sourceAlreadyBilled(
        invoices,
        "CONSULTATION",
        consultation.id
      )
    ) {
      continue;
    }

    const invoice =
      findOrCreateOpenInvoice(
        invoices,
        {
          id:
            consultation.patientId,

          number:
            consultation.patientNumber,

          name:
            consultation.patientName,
        }
      );

    addItem(
      invoice,
      {
        sourceType:
          "CONSULTATION",

        sourceId:
          consultation.id,

        description:
          "Consultation médicale",

        amount:
          TARIFFS.CONSULTATION,
      }
    );
  }

  for (
    const request
    of laboratoryRequests
  ) {
    if (
      sourceAlreadyBilled(
        invoices,
        "LABORATORY",
        request.id
      )
    ) {
      continue;
    }

    const invoice =
      findOrCreateOpenInvoice(
        invoices,
        {
          id:
            request.patientId,

          number:
            request.patientNumber,

          name:
            request.patientName,
        }
      );

    addItem(
      invoice,
      {
        sourceType:
          "LABORATORY",

        sourceId:
          request.id,

        description:
          `Laboratoire - ${request.requestNotes}`,

        amount:
          TARIFFS.LABORATORY,
      }
    );
  }

  for (
    const admission
    of admissions
  ) {
    if (
      admission.status ===
      "WAITING"
    ) {
      continue;
    }

    if (
      sourceAlreadyBilled(
        invoices,
        "HOSPITALIZATION",
        admission.id
      )
    ) {
      continue;
    }

    const invoice =
      findOrCreateOpenInvoice(
        invoices,
        {
          id:
            admission.patientId,

          number:
            admission.patientNumber,

          name:
            admission.patientName,
        }
      );

    addItem(
      invoice,
      {
        sourceType:
          "HOSPITALIZATION",

        sourceId:
          admission.id,

        description:
          "Hospitalisation et hébergement",

        amount:
          TARIFFS.HOSPITALIZATION,
      }
    );
  }

  for (
    const invoice
    of invoices
  ) {
    invoice.status =
      calculateStatus(invoice);
  }

  saveInvoices(invoices);

  return invoices;
}

export async function listInvoices():
  Promise<Invoice[]> {
  return synchronizeBilling();
}

export async function getInvoice(
  invoiceId: string
): Promise<Invoice | null> {
  await synchronizeBilling();

  return (
    loadInvoices().find(
      (invoice) =>
        invoice.id === invoiceId
    ) ?? null
  );
}

export async function registerPayment(
  invoiceId: string,
  amount: number,
  method: PaymentMethod,
  reference?: string
): Promise<Invoice> {
  const invoices =
    loadInvoices();

  const index =
    invoices.findIndex(
      (invoice) =>
        invoice.id === invoiceId
    );

  if (index === -1) {
    throw new Error(
      "Facture introuvable"
    );
  }

  const invoice =
    invoices[index];

  const balance =
    invoiceBalance(invoice);

  if (
    !Number.isFinite(amount) ||
    amount <= 0
  ) {
    throw new Error(
      "Montant de paiement invalide"
    );
  }

  if (amount > balance) {
    throw new Error(
      "Le montant dépasse le solde restant"
    );
  }

  const payment:
    InvoicePayment = {
      id: crypto.randomUUID(),

      amount,

      method,

      reference:
        reference?.trim(),

      paidAt:
        new Date().toISOString(),
    };

  invoice.payments.push(
    payment
  );

  invoice.updatedAt =
    new Date().toISOString();

  invoice.status =
    calculateStatus(invoice);

  invoices[index] =
    invoice;

  saveInvoices(invoices);

  return invoice;
}
