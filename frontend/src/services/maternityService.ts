import {
  closePatientJourney,
  listPatients,
} from "./patientService";

import {
  addServiceCharge,
} from "./billingService";

import type {
  DeliveryType,
  MaternityCase,
  NewbornSex,
} from "../types/maternity";

const STORAGE_KEY =
  "hospitalis_maternity_cases";

const MATERNITY_TARIFF =
  80000;

function loadCases():
  MaternityCase[] {
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
    ) as MaternityCase[];
  } catch {
    return [];
  }
}

function saveCases(
  cases: MaternityCase[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(cases)
  );
}

export async function synchronizeMaternityCases():
  Promise<MaternityCase[]> {
  const patients =
    await listPatients();

  const cases =
    loadCases();

  let changed = false;

  for (const patient of patients) {
    const patientCases =
      cases.filter(
        (item) =>
          item.patientId ===
          patient.id
      );

    const latestDischarged =
      patientCases
        .filter(
          (item) =>
            item.status ===
              "DISCHARGED" &&
            item.dischargedAt
        )
        .sort(
          (a, b) =>
            new Date(
              b.dischargedAt!
            ).getTime() -
            new Date(
              a.dischargedAt!
            ).getTime()
        )[0];

    const latestMaternityRoute =
      (patient.history ?? [])
        .filter(
          (event) =>
            event.service ===
              "Maternité" &&
            (
              event.type ===
                "CHECK_IN" ||
              event.type ===
                "ORIENTED" ||
              event.type ===
                "TRANSFER"
            )
        )
        .sort(
          (a, b) =>
            new Date(
              b.at
            ).getTime() -
            new Date(
              a.at
            ).getTime()
        )[0];

    if (
      latestDischarged &&
      (
        !latestMaternityRoute ||
        new Date(
          latestMaternityRoute.at
        ).getTime() <=
        new Date(
          latestDischarged
            .dischargedAt!
        ).getTime()
      )
    ) {
      for (
        let index =
          cases.length - 1;
        index >= 0;
        index--
      ) {
        const item =
          cases[index];

        if (
          item.patientId ===
            patient.id &&
          item.status ===
            "WAITING" &&
          new Date(
            item.requestedAt
          ).getTime() >
          new Date(
            latestDischarged
              .dischargedAt!
          ).getTime()
        ) {
          cases.splice(
            index,
            1
          );

          changed = true;
        }
      }
    }

    if (
      patient.targetService !==
        "Maternité" ||
      patient.arrivalStatus !==
        "ORIENTED"
    ) {
      continue;
    }

    const activeCase =
      cases.some(
        (item) =>
          item.patientId ===
            patient.id &&
          item.status !==
            "DISCHARGED"
      );

    if (activeCase) {
      continue;
    }

    if (
      latestDischarged &&
      (
        !latestMaternityRoute ||
        new Date(
          latestMaternityRoute.at
        ).getTime() <=
        new Date(
          latestDischarged
            .dischargedAt!
        ).getTime()
      )
    ) {
      continue;
    }

    cases.unshift({
      id:
        crypto.randomUUID(),

      patientId:
        patient.id,

      patientNumber:
        patient.patientNumber,

      patientName:
        `${patient.firstName} ${patient.lastName}`,

      reason:
        patient.arrivalReason ??
        "Prise en charge maternité",

      status:
        "WAITING",

      gestationalAgeWeeks:
        "",

      gravida:
        "",

      para:
        "",

      bloodGroup:
        "",

      estimatedDueDate:
        "",

      riskNotes:
        "",

      admissionNotes:
        "",

      requestedAt:
        new Date().toISOString(),
    });

    changed = true;
  }

  if (changed) {
    saveCases(cases);
  }

  return cases;
}

export async function listMaternityCases():
  Promise<MaternityCase[]> {
  await synchronizeMaternityCases();

  return loadCases();
}

export async function getMaternityCase(
  caseId: string
): Promise<MaternityCase | null> {
  await synchronizeMaternityCases();

  return (
    loadCases().find(
      (item) =>
        item.id === caseId
    ) ?? null
  );
}

export async function saveMaternityInformation(
  caseId: string,
  input: {
    gestationalAgeWeeks: string;
    gravida: string;
    para: string;
    bloodGroup: string;
    estimatedDueDate: string;
    riskNotes: string;
    admissionNotes: string;
  }
): Promise<MaternityCase> {
  const cases =
    loadCases();

  const index =
    cases.findIndex(
      (item) =>
        item.id === caseId
    );

  if (index === -1) {
    throw new Error(
      "Dossier maternité introuvable"
    );
  }

  cases[index] = {
    ...cases[index],
    ...input,
  };

  saveCases(cases);

  return cases[index];
}

export async function admitMaternityPatient(
  caseId: string
): Promise<MaternityCase> {
  const cases =
    loadCases();

  const index =
    cases.findIndex(
      (item) =>
        item.id === caseId
    );

  if (index === -1) {
    throw new Error(
      "Dossier maternité introuvable"
    );
  }

  if (
    cases[index].status !==
    "WAITING"
  ) {
    throw new Error(
      "Cette patiente a déjà été admise"
    );
  }

  cases[index] = {
    ...cases[index],

    status:
      "ADMITTED",

    admittedAt:
      new Date().toISOString(),
  };

  saveCases(cases);

  return cases[index];
}

export async function startLabor(
  caseId: string
): Promise<MaternityCase> {
  const cases =
    loadCases();

  const index =
    cases.findIndex(
      (item) =>
        item.id === caseId
    );

  if (index === -1) {
    throw new Error(
      "Dossier maternité introuvable"
    );
  }

  if (
    cases[index].status !==
    "ADMITTED"
  ) {
    throw new Error(
      "La patiente doit être admise avant le début du travail"
    );
  }

  cases[index] = {
    ...cases[index],

    status:
      "IN_LABOR",

    laborStartedAt:
      new Date().toISOString(),
  };

  saveCases(cases);

  return cases[index];
}

export async function registerDelivery(
  caseId: string,
  input: {
    deliveryType: DeliveryType;

    deliveryNotes: string;

    newbornName: string;
    newbornSex: NewbornSex;

    newbornWeightGrams: number;
    newbornLengthCm: number;

    apgar1: number;
    apgar5: number;

    newbornObservations: string;
  }
): Promise<MaternityCase> {
  const cases =
    loadCases();

  const index =
    cases.findIndex(
      (item) =>
        item.id === caseId
    );

  if (index === -1) {
    throw new Error(
      "Dossier maternité introuvable"
    );
  }

  if (
    cases[index].status !==
    "IN_LABOR"
  ) {
    throw new Error(
      "Le travail doit être commencé avant d'enregistrer l'accouchement"
    );
  }

  if (
    !Number.isFinite(
      input.newbornWeightGrams
    ) ||
    input.newbornWeightGrams <= 0
  ) {
    throw new Error(
      "Poids du nouveau-né invalide"
    );
  }

  const deliveredAt =
    new Date().toISOString();

  cases[index] = {
    ...cases[index],

    status:
      "DELIVERED",

    deliveryType:
      input.deliveryType,

    deliveryNotes:
      input.deliveryNotes.trim(),

    deliveredAt,

    newborn: {
      id:
        crypto.randomUUID(),

      name:
        input.newbornName.trim(),

      sex:
        input.newbornSex,

      weightGrams:
        input.newbornWeightGrams,

      lengthCm:
        input.newbornLengthCm,

      apgar1:
        input.apgar1,

      apgar5:
        input.apgar5,

      observations:
        input.newbornObservations.trim(),

      bornAt:
        deliveredAt,
    },
  };

  saveCases(cases);

  await addServiceCharge({
    patientId:
      cases[index].patientId,

    patientNumber:
      cases[index].patientNumber,

    patientName:
      cases[index].patientName,

    sourceType:
      "MATERNITY",

    sourceId:
      cases[index].id,

    description:
      "Prise en charge maternité et accouchement",

    amount:
      MATERNITY_TARIFF,
  });

  return cases[index];
}

export async function dischargeMaternityPatient(
  caseId: string,
  notes: string
): Promise<MaternityCase> {
  const cases =
    loadCases();

  const index =
    cases.findIndex(
      (item) =>
        item.id === caseId
    );

  if (index === -1) {
    throw new Error(
      "Dossier maternité introuvable"
    );
  }

  if (
    cases[index].status !==
    "DELIVERED"
  ) {
    throw new Error(
      "L'accouchement doit être enregistré avant la sortie"
    );
  }

  cases[index] = {
    ...cases[index],

    status:
      "DISCHARGED",

    dischargeNotes:
      notes.trim(),

    dischargedAt:
      new Date().toISOString(),
  };

  saveCases(cases);

  await closePatientJourney(
    cases[index].patientId,
    "Sortie de maternité - parcours clôturé"
  );

  return cases[index];
}
