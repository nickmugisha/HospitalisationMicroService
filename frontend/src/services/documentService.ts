import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";

import type {
  LaboratoryRequest,
} from "../types/laboratory";

import type {
  Invoice,
  InvoicePayment,
} from "../types/billing";

import type {
  Medication,
  PharmacyOrder,
} from "../types/pharmacy";

import type {
  MaternityCase,
} from "../types/maternity";


import type {
  Appointment,
} from "../types/appointment";

import {
  invoiceBalance,
  invoicePaid,
  invoiceTotal,
} from "./billingService";

function formatDate(
  value?: string
): string {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      dateStyle: "medium",
      timeStyle: "short",
    }
  ).format(new Date(value));
}

function formatMoney(
  value: number
): string {
  const formatted =
    new Intl.NumberFormat(
      "fr-FR"
    )
      .format(value)
      .replace(/\u202f|\u00a0/g, " ");

  return `${formatted} BIF`;
}

function paymentMethodLabel(
  method: string
): string {
  switch (method) {
    case "CASH":
      return "Especes";

    case "MOBILE_MONEY":
      return "Mobile Money";

    case "BANK":
      return "Banque";

    case "CARD":
      return "Carte";

    default:
      return method;
  }
}

function addHeader(
  doc: jsPDF,
  title: string,
  subtitle?: string
) {
  doc.setFillColor(
    17,
    125,
    105
  );

  doc.rect(
    0,
    0,
    210,
    34,
    "F"
  );

  doc.setTextColor(
    255,
    255,
    255
  );

  doc.setFontSize(18);

  doc.text(
    "HOSPITALIS",
    15,
    14
  );

  doc.setFontSize(8);

  doc.text(
    "Plateforme Hospitaliere MicroServices",
    15,
    20
  );

  doc.setFontSize(11);

  doc.text(
    title,
    195,
    14,
    {
      align: "right",
    }
  );

  if (subtitle) {
    doc.setFontSize(8);

    doc.text(
      subtitle,
      195,
      20,
      {
        align: "right",
      }
    );
  }

  doc.setTextColor(
    35,
    52,
    68
  );
}

function addFooter(
  doc: jsPDF
) {
  const pages =
    doc.getNumberOfPages();

  for (
    let page = 1;
    page <= pages;
    page++
  ) {
    doc.setPage(page);

    doc.setDrawColor(
      220,
      226,
      232
    );

    doc.line(
      15,
      282,
      195,
      282
    );

    doc.setFontSize(7);

    doc.setTextColor(
      120,
      130,
      140
    );

    doc.text(
      "HOSPITALIS MicroServices - Document genere electroniquement",
      15,
      288
    );

    doc.text(
      `Page ${page}/${pages}`,
      195,
      288,
      {
        align: "right",
      }
    );
  }
}

function getLastTableY(
  doc: jsPDF,
  fallback: number
) {
  const extended =
    doc as unknown as {
      lastAutoTable?: {
        finalY: number;
      };
    };

  return (
    extended.lastAutoTable
      ?.finalY ??
    fallback
  );
}

function openPdfForPrint(
  doc: jsPDF
) {
  const blob =
    doc.output("blob");

  const url =
    URL.createObjectURL(
      blob
    );

  const printWindow =
    window.open(
      url,
      "_blank"
    );

  if (!printWindow) {
    URL.revokeObjectURL(
      url
    );

    throw new Error(
      "Le navigateur a bloque la fenetre d'impression."
    );
  }

  setTimeout(() => {
    printWindow.focus();
    printWindow.print();

    setTimeout(() => {
      URL.revokeObjectURL(
        url
      );
    }, 5000);
  }, 1000);
}

/* =========================================================
   LABORATOIRE
========================================================= */

function buildLaboratoryPdf(
  request: LaboratoryRequest
) {
  const doc =
    new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

  addHeader(
    doc,
    "RESULTATS DE LABORATOIRE",
    request.patientNumber
  );

  doc.setFontSize(15);

  doc.text(
    request.patientName,
    15,
    48
  );

  doc.setFontSize(9);

  doc.setTextColor(
    90,
    105,
    118
  );

  doc.text(
    `Numero patient : ${request.patientNumber}`,
    15,
    56
  );

  doc.text(
    `Demande : ${request.requestNotes}`,
    15,
    62
  );

  doc.text(
    `Demande le : ${formatDate(
      request.requestedAt
    )}`,
    15,
    68
  );

  doc.text(
    `Resultats valides le : ${formatDate(
      request.completedAt
    )}`,
    15,
    74
  );

  doc.setTextColor(
    35,
    52,
    68
  );

  autoTable(doc, {
    startY: 84,

    head: [[
      "Analyse",
      "Resultat",
      "Unite",
      "Valeurs de reference",
      "Interpretation",
    ]],

    body:
      request.tests.map(
        (test) => [
          test.name || "—",
          test.result || "—",
          test.unit || "—",
          test.referenceRange ||
            "—",
          test.abnormal
            ? "ANORMAL"
            : "Normal",
        ]
      ),

    theme: "grid",

    styles: {
      fontSize: 8,
      cellPadding: 3,
    },

    headStyles: {
      fillColor: [
        17,
        125,
        105,
      ],
      textColor: 255,
    },
  });

  const finalY =
    getLastTableY(
      doc,
      100
    );

  doc.setFontSize(8);

  doc.setTextColor(
    105,
    115,
    125
  );

  doc.text(
    "Important : les resultats doivent etre interpretes par un professionnel de sante.",
    15,
    finalY + 12
  );

  addFooter(doc);

  return doc;
}

export function exportLaboratoryResultPdf(
  request: LaboratoryRequest
) {
  if (
    request.status !==
    "COMPLETED"
  ) {
    throw new Error(
      "Les resultats doivent etre valides avant l'export PDF."
    );
  }

  const doc =
    buildLaboratoryPdf(
      request
    );

  doc.save(
    `Laboratoire_${request.patientNumber}.pdf`
  );
}

export function printLaboratoryResult(
  request: LaboratoryRequest
) {
  if (
    request.status !==
    "COMPLETED"
  ) {
    throw new Error(
      "Les resultats doivent etre valides avant impression."
    );
  }

  openPdfForPrint(
    buildLaboratoryPdf(
      request
    )
  );
}

/* =========================================================
   FACTURATION
========================================================= */

function buildInvoicePdf(
  invoice: Invoice
) {
  const doc =
    new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

  addHeader(
    doc,
    "FACTURE PATIENT",
    invoice.invoiceNumber
  );

  doc.setFontSize(15);

  doc.text(
    invoice.patientName,
    15,
    48
  );

  doc.setFontSize(9);

  doc.setTextColor(
    90,
    105,
    118
  );

  doc.text(
    `Numero patient : ${invoice.patientNumber}`,
    15,
    56
  );

  doc.text(
    `Numero facture : ${invoice.invoiceNumber}`,
    15,
    62
  );

  doc.text(
    `Date : ${formatDate(
      invoice.createdAt
    )}`,
    15,
    68
  );

  doc.text(
    `Statut : ${invoice.status}`,
    15,
    74
  );

  autoTable(doc, {
    startY: 84,

    head: [[
      "Prestation",
      "Qte",
      "Prix unitaire",
      "Total",
    ]],

    body:
      invoice.items.map(
        (item) => [
          item.description,
          String(
            item.quantity
          ),
          formatMoney(
            item.unitPrice
          ),
          formatMoney(
            item.total
          ),
        ]
      ),

    theme: "grid",

    styles: {
      fontSize: 8,
      cellPadding: 3,
    },

    headStyles: {
      fillColor: [
        17,
        125,
        105,
      ],
      textColor: 255,
    },
  });

  let y =
    getLastTableY(
      doc,
      100
    ) + 12;

  doc.setFontSize(10);

  doc.setTextColor(
    35,
    52,
    68
  );

  doc.text(
    "Total facture",
    135,
    y
  );

  doc.text(
    formatMoney(
      invoiceTotal(
        invoice
      )
    ),
    195,
    y,
    {
      align: "right",
    }
  );

  y += 7;

  doc.text(
    "Montant paye",
    135,
    y
  );

  doc.text(
    formatMoney(
      invoicePaid(
        invoice
      )
    ),
    195,
    y,
    {
      align: "right",
    }
  );

  y += 7;

  doc.setFontSize(12);

  doc.text(
    "Reste a payer",
    135,
    y
  );

  doc.text(
    formatMoney(
      invoiceBalance(
        invoice
      )
    ),
    195,
    y,
    {
      align: "right",
    }
  );

  if (
    invoice.payments.length >
    0
  ) {
    y += 15;

    doc.setFontSize(11);

    doc.text(
      "Historique des paiements",
      15,
      y
    );

    autoTable(doc, {
      startY: y + 5,

      head: [[
        "Date",
        "Mode",
        "Reference",
        "Montant",
      ]],

      body:
        invoice.payments.map(
          (payment) => [
            formatDate(
              payment.paidAt
            ),

            paymentMethodLabel(
              payment.method
            ),

            payment.reference ||
              "—",

            formatMoney(
              payment.amount
            ),
          ]
        ),

      theme: "grid",

      styles: {
        fontSize: 8,
      },

      headStyles: {
        fillColor: [
          18,
          60,
          77,
        ],
        textColor: 255,
      },
    });
  }

  addFooter(doc);

  return doc;
}

export function exportInvoicePdf(
  invoice: Invoice
) {
  const doc =
    buildInvoicePdf(
      invoice
    );

  doc.save(
    `${invoice.invoiceNumber}.pdf`
  );
}

export function printInvoice(
  invoice: Invoice
) {
  openPdfForPrint(
    buildInvoicePdf(
      invoice
    )
  );
}

/* =========================================================
   RECU DE PAIEMENT
========================================================= */

function buildPaymentReceiptPdf(
  invoice: Invoice,
  payment: InvoicePayment
) {
  const doc =
    new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a5",
    });

  doc.setFillColor(
    17,
    125,
    105
  );

  doc.rect(
    0,
    0,
    148,
    32,
    "F"
  );

  doc.setTextColor(
    255,
    255,
    255
  );

  doc.setFontSize(16);

  doc.text(
    "HOSPITALIS",
    12,
    14
  );

  doc.setFontSize(9);

  doc.text(
    "RECU DE PAIEMENT",
    136,
    14,
    {
      align: "right",
    }
  );

  doc.setTextColor(
    35,
    52,
    68
  );

  doc.setFontSize(13);

  doc.text(
    invoice.patientName,
    12,
    47
  );

  doc.setFontSize(9);

  const rows = [
    [
      "Patient",
      invoice.patientNumber,
    ],
    [
      "Facture",
      invoice.invoiceNumber,
    ],
    [
      "Date",
      formatDate(
        payment.paidAt
      ),
    ],
    [
      "Mode",
      paymentMethodLabel(
        payment.method
      ),
    ],
    [
      "Reference",
      payment.reference ||
        "—",
    ],
    [
      "Montant paye",
      formatMoney(
        payment.amount
      ),
    ],
    [
      "Reste a payer",
      formatMoney(
        invoiceBalance(
          invoice
        )
      ),
    ],
  ];

  autoTable(doc, {
    startY: 56,

    body: rows,

    theme: "grid",

    styles: {
      fontSize: 9,
      cellPadding: 4,
    },

    columnStyles: {
      0: {
        fontStyle: "bold",
      },
    },
  });

  doc.setFontSize(8);

  doc.setTextColor(
    105,
    115,
    125
  );

  doc.text(
    "Merci. Ce recu confirme l'enregistrement du paiement dans HOSPITALIS.",
    12,
    135
  );

  return doc;
}

export function exportPaymentReceiptPdf(
  invoice: Invoice,
  payment: InvoicePayment
) {
  buildPaymentReceiptPdf(
    invoice,
    payment
  ).save(
    `RECU_${invoice.invoiceNumber}.pdf`
  );
}

export function printPaymentReceipt(
  invoice: Invoice,
  payment: InvoicePayment
) {
  openPdfForPrint(
    buildPaymentReceiptPdf(
      invoice,
      payment
    )
  );
}


/* =========================================================
   PHARMACIE
========================================================= */

function buildPharmacyDeliveryPdf(
  order: PharmacyOrder,
  medications: Medication[]
) {
  const doc =
    new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

  addHeader(
    doc,
    "BON DE DELIVRANCE PHARMACIE",
    order.patientNumber
  );

  doc.setFontSize(15);

  doc.text(
    order.patientName,
    15,
    48
  );

  doc.setFontSize(9);

  doc.setTextColor(
    90,
    105,
    118
  );

  doc.text(
    `Numero patient : ${order.patientNumber}`,
    15,
    56
  );

  doc.text(
    `Date de delivrance : ${formatDate(
      order.dispensedAt
    )}`,
    15,
    62
  );

  doc.setTextColor(
    35,
    52,
    68
  );

  autoTable(doc, {
    startY: 72,

    head: [[
      "Medicament",
      "Dosage",
      "Frequence",
      "Duree",
      "Quantite",
    ]],

    body:
      order.items.map(
        (item) => {
          const medication =
            medications.find(
              (current) =>
                current.id ===
                item.medicationId
            );

          return [
            medication
              ? `${medication.name} ${medication.strength}`
              : item.prescribedName,

            item.dosage || "—",

            item.frequency || "—",

            item.duration || "—",

            String(
              item.dispensedQuantity
            ),
          ];
        }
      ),

    theme: "grid",

    styles: {
      fontSize: 8,
      cellPadding: 3,
    },

    headStyles: {
      fillColor: [
        17,
        125,
        105,
      ],
      textColor: 255,
    },
  });

  const finalY =
    getLastTableY(
      doc,
      100
    );

  doc.setFontSize(8);

  doc.setTextColor(
    105,
    115,
    125
  );

  doc.text(
    "Document de tracabilite de la delivrance pharmaceutique.",
    15,
    finalY + 12
  );

  addFooter(doc);

  return doc;
}

export function exportPharmacyDeliveryPdf(
  order: PharmacyOrder,
  medications: Medication[]
) {
  if (
    order.status !==
    "DISPENSED"
  ) {
    throw new Error(
      "L'ordonnance doit etre entierement delivree avant export."
    );
  }

  buildPharmacyDeliveryPdf(
    order,
    medications
  ).save(
    `PHARMACIE_${order.patientNumber}.pdf`
  );
}

export function printPharmacyDelivery(
  order: PharmacyOrder,
  medications: Medication[]
) {
  if (
    order.status !==
    "DISPENSED"
  ) {
    throw new Error(
      "L'ordonnance doit etre entierement delivree avant impression."
    );
  }

  openPdfForPrint(
    buildPharmacyDeliveryPdf(
      order,
      medications
    )
  );
}


/* =========================================================
   MATERNITE
========================================================= */

function buildMaternitySummaryPdf(
  maternity: MaternityCase
) {
  const doc =
    new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

  addHeader(
    doc,
    "COMPTE-RENDU MATERNITE",
    maternity.patientNumber
  );

  doc.setFontSize(15);

  doc.text(
    maternity.patientName,
    15,
    48
  );

  doc.setFontSize(9);

  doc.setTextColor(
    90,
    105,
    118
  );

  doc.text(
    `Numero patient : ${maternity.patientNumber}`,
    15,
    56
  );

  doc.text(
    `Admission : ${formatDate(
      maternity.admittedAt
    )}`,
    15,
    62
  );

  doc.text(
    `Accouchement : ${formatDate(
      maternity.deliveredAt
    )}`,
    15,
    68
  );

  doc.setTextColor(
    35,
    52,
    68
  );

  autoTable(doc, {
    startY: 78,

    body: [
      [
        "Age gestationnel",
        maternity.gestationalAgeWeeks
          ? `${maternity.gestationalAgeWeeks} semaines`
          : "—",
      ],

      [
        "Gravida / Para",
        `${maternity.gravida || "—"} / ${maternity.para || "—"}`,
      ],

      [
        "Groupe sanguin",
        maternity.bloodGroup || "—",
      ],

      [
        "Type d'accouchement",
        maternity.deliveryType || "—",
      ],

      [
        "Facteurs de risque",
        maternity.riskNotes || "Aucun",
      ],

      [
        "Notes d'accouchement",
        maternity.deliveryNotes || "—",
      ],
    ],

    theme: "grid",

    styles: {
      fontSize: 8,
      cellPadding: 3,
    },

    columnStyles: {
      0: {
        fontStyle: "bold",
        cellWidth: 48,
      },
    },
  });

  let y =
    getLastTableY(
      doc,
      110
    ) + 12;

  if (maternity.newborn) {
    doc.setFontSize(12);

    doc.text(
      "Nouveau-ne",
      15,
      y
    );

    y += 6;

    autoTable(doc, {
      startY: y,

      head: [[
        "Nom",
        "Sexe",
        "Poids",
        "Taille",
        "APGAR 1'",
        "APGAR 5'",
      ]],

      body: [[
        maternity.newborn.name ||
          "Nouveau-ne",

        maternity.newborn.sex ===
        "M"
          ? "Masculin"
          : "Feminin",

        `${maternity.newborn.weightGrams} g`,

        `${maternity.newborn.lengthCm} cm`,

        String(
          maternity.newborn.apgar1
        ),

        String(
          maternity.newborn.apgar5
        ),
      ]],

      theme: "grid",

      styles: {
        fontSize: 8,
        cellPadding: 3,
      },

      headStyles: {
        fillColor: [
          17,
          125,
          105,
        ],
        textColor: 255,
      },
    });

    y =
      getLastTableY(
        doc,
        y + 20
      ) + 10;

    doc.setFontSize(8);

    doc.text(
      `Observations nouveau-ne : ${maternity.newborn.observations || "Aucune"}`,
      15,
      y,
      {
        maxWidth: 180,
      }
    );
  }

  if (
    maternity.dischargeNotes
  ) {
    y += 16;

    doc.setFontSize(11);

    doc.text(
      "Recommandations de sortie",
      15,
      y
    );

    y += 6;

    doc.setFontSize(8);

    doc.text(
      maternity.dischargeNotes,
      15,
      y,
      {
        maxWidth: 180,
      }
    );
  }

  addFooter(doc);

  return doc;
}

export function exportMaternitySummaryPdf(
  maternity: MaternityCase
) {
  if (
    maternity.status !==
      "DELIVERED" &&
    maternity.status !==
      "DISCHARGED"
  ) {
    throw new Error(
      "L'accouchement doit etre enregistre avant l'export."
    );
  }

  buildMaternitySummaryPdf(
    maternity
  ).save(
    `MATERNITE_${maternity.patientNumber}.pdf`
  );
}

export function printMaternitySummary(
  maternity: MaternityCase
) {
  if (
    maternity.status !==
      "DELIVERED" &&
    maternity.status !==
      "DISCHARGED"
  ) {
    throw new Error(
      "L'accouchement doit etre enregistre avant impression."
    );
  }

  openPdfForPrint(
    buildMaternitySummaryPdf(
      maternity
    )
  );
}


/* =========================================================
   RENDEZ-VOUS
========================================================= */

function appointmentStatusLabel(
  status: Appointment["status"]
): string {
  switch (status) {
    case "SCHEDULED":
      return "Planifie";

    case "CONFIRMED":
      return "Confirme";

    case "CHECKED_IN":
      return "Patient present";

    case "COMPLETED":
      return "Termine";

    case "CANCELLED":
      return "Annule";

    case "NO_SHOW":
      return "Absent";
  }
}

function buildAppointmentPdf(
  appointment: Appointment
) {
  const doc =
    new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a5",
    });

  doc.setFillColor(
    17,
    125,
    105
  );

  doc.rect(
    0,
    0,
    148,
    34,
    "F"
  );

  doc.setTextColor(
    255,
    255,
    255
  );

  doc.setFontSize(16);

  doc.text(
    "HOSPITALIS",
    12,
    14
  );

  doc.setFontSize(8);

  doc.text(
    "TICKET DE RENDEZ-VOUS",
    136,
    14,
    {
      align: "right",
    }
  );

  doc.text(
    appointment.appointmentNumber,
    136,
    21,
    {
      align: "right",
    }
  );

  doc.setTextColor(
    35,
    52,
    68
  );

  doc.setFontSize(14);

  doc.text(
    appointment.patientName,
    12,
    48
  );

  autoTable(doc, {
    startY: 56,

    body: [
      [
        "Numero patient",
        appointment.patientNumber,
      ],

      [
        "Date",
        appointment.date,
      ],

      [
        "Heure",
        appointment.time,
      ],

      [
        "Duree",
        `${appointment.durationMinutes} minutes`,
      ],

      [
        "Service",
        appointment.service,
      ],

      [
        "Medecin",
        appointment.doctorName,
      ],

      [
        "Motif",
        appointment.reason,
      ],

      [
        "Statut",
        appointmentStatusLabel(
          appointment.status
        ),
      ],
    ],

    theme: "grid",

    styles: {
      fontSize: 8,
      cellPadding: 3.5,
    },

    columnStyles: {
      0: {
        fontStyle: "bold",
        cellWidth: 38,
      },
    },
  });

  const y =
    getLastTableY(
      doc,
      100
    ) + 10;

  if (appointment.notes) {
    doc.setFontSize(8);

    doc.setTextColor(
      90,
      105,
      118
    );

    doc.text(
      `Notes : ${appointment.notes}`,
      12,
      y,
      {
        maxWidth: 124,
      }
    );
  }

  doc.setFontSize(7);

  doc.setTextColor(
    110,
    120,
    130
  );

  doc.text(
    "Veuillez vous presenter a l'accueil avant l'heure du rendez-vous.",
    12,
    196
  );

  return doc;
}

export function exportAppointmentPdf(
  appointment: Appointment
) {
  buildAppointmentPdf(
    appointment
  ).save(
    `${appointment.appointmentNumber}.pdf`
  );
}

export function printAppointment(
  appointment: Appointment
) {
  openPdfForPrint(
    buildAppointmentPdf(
      appointment
    )
  );
}
