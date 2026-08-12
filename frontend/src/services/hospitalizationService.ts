import {
  listConsultations,
} from "./consultationService";

import type {
  HospitalBed,
  HospitalizationAdmission,
} from "../types/hospitalization";

const ADMISSIONS_KEY =
  "hospitalis_admissions";

const BEDS_KEY =
  "hospitalis_beds";

const defaultBeds: HospitalBed[] = [
  {
    id: "MED-101-A",
    ward: "Médecine interne",
    roomNumber: "101",
    bedNumber: "A",
  },
  {
    id: "MED-101-B",
    ward: "Médecine interne",
    roomNumber: "101",
    bedNumber: "B",
  },
  {
    id: "MED-102-A",
    ward: "Médecine interne",
    roomNumber: "102",
    bedNumber: "A",
  },
  {
    id: "MED-102-B",
    ward: "Médecine interne",
    roomNumber: "102",
    bedNumber: "B",
  },
  {
    id: "CHIR-201-A",
    ward: "Chirurgie",
    roomNumber: "201",
    bedNumber: "A",
  },
  {
    id: "CHIR-201-B",
    ward: "Chirurgie",
    roomNumber: "201",
    bedNumber: "B",
  },
  {
    id: "CHIR-202-A",
    ward: "Chirurgie",
    roomNumber: "202",
    bedNumber: "A",
  },
  {
    id: "CHIR-202-B",
    ward: "Chirurgie",
    roomNumber: "202",
    bedNumber: "B",
  },
];

function loadAdmissions():
  HospitalizationAdmission[] {
  const stored =
    localStorage.getItem(
      ADMISSIONS_KEY
    );

  if (!stored) {
    return [];
  }

  try {
    return JSON.parse(
      stored
    ) as HospitalizationAdmission[];
  } catch {
    return [];
  }
}

function saveAdmissions(
  admissions: HospitalizationAdmission[]
) {
  localStorage.setItem(
    ADMISSIONS_KEY,
    JSON.stringify(admissions)
  );
}

function loadBeds():
  HospitalBed[] {
  const stored =
    localStorage.getItem(
      BEDS_KEY
    );

  if (!stored) {
    localStorage.setItem(
      BEDS_KEY,
      JSON.stringify(defaultBeds)
    );

    return defaultBeds;
  }

  try {
    return JSON.parse(
      stored
    ) as HospitalBed[];
  } catch {
    return defaultBeds;
  }
}

function saveBeds(
  beds: HospitalBed[]
) {
  localStorage.setItem(
    BEDS_KEY,
    JSON.stringify(beds)
  );
}

export async function synchronizeHospitalizationRequests():
  Promise<HospitalizationAdmission[]> {
  const consultations =
    await listConsultations();

  const admissions =
    loadAdmissions();

  let changed = false;

  for (const consultation of consultations) {
    if (
      !consultation
        .hospitalizationRequested
    ) {
      continue;
    }

    const exists =
      admissions.some(
        (admission) =>
          admission.consultationId ===
          consultation.id
      );

    if (exists) {
      continue;
    }

    admissions.unshift({
      id: crypto.randomUUID(),

      consultationId:
        consultation.id,

      patientId:
        consultation.patientId,

      patientNumber:
        consultation.patientNumber,

      patientName:
        consultation.patientName,

      reason:
        consultation
          .hospitalizationReason ??
        "Hospitalisation demandée",

      status: "WAITING",

      requestedAt:
        new Date().toISOString(),
    });

    changed = true;
  }

  if (changed) {
    saveAdmissions(admissions);
  }

  return admissions;
}

export async function listAdmissions():
  Promise<HospitalizationAdmission[]> {
  await synchronizeHospitalizationRequests();

  return loadAdmissions();
}

export async function listHospitalBeds():
  Promise<HospitalBed[]> {
  return loadBeds();
}

export async function getAdmission(
  admissionId: string
): Promise<HospitalizationAdmission | null> {
  await synchronizeHospitalizationRequests();

  return (
    loadAdmissions().find(
      (admission) =>
        admission.id === admissionId
    ) ?? null
  );
}

export async function admitPatient(
  admissionId: string,
  bedId: string,
  notes: string
): Promise<HospitalizationAdmission> {
  const admissions =
    loadAdmissions();

  const beds =
    loadBeds();

  const admissionIndex =
    admissions.findIndex(
      (admission) =>
        admission.id === admissionId
    );

  if (admissionIndex === -1) {
    throw new Error(
      "Demande d'hospitalisation introuvable"
    );
  }

  const bedIndex =
    beds.findIndex(
      (bed) =>
        bed.id === bedId
    );

  if (bedIndex === -1) {
    throw new Error(
      "Lit introuvable"
    );
  }

  if (
    beds[bedIndex]
      .occupiedByAdmissionId
  ) {
    throw new Error(
      "Ce lit est déjà occupé"
    );
  }

  if (
    admissions[admissionIndex]
      .status !== "WAITING"
  ) {
    throw new Error(
      "Ce patient a déjà été admis"
    );
  }

  const bed =
    beds[bedIndex];

  admissions[admissionIndex] = {
    ...admissions[admissionIndex],

    status: "ADMITTED",

    bedId: bed.id,
    ward: bed.ward,
    roomNumber:
      bed.roomNumber,
    bedNumber:
      bed.bedNumber,

    admissionNotes:
      notes.trim(),

    admittedAt:
      new Date().toISOString(),
  };

  beds[bedIndex] = {
    ...bed,

    occupiedByAdmissionId:
      admissionId,
  };

  saveAdmissions(admissions);
  saveBeds(beds);

  return admissions[
    admissionIndex
  ];
}

export async function dischargePatient(
  admissionId: string,
  notes: string
): Promise<HospitalizationAdmission> {
  const admissions =
    loadAdmissions();

  const beds =
    loadBeds();

  const index =
    admissions.findIndex(
      (admission) =>
        admission.id === admissionId
    );

  if (index === -1) {
    throw new Error(
      "Admission introuvable"
    );
  }

  const admission =
    admissions[index];

  if (
    admission.status !==
    "ADMITTED"
  ) {
    throw new Error(
      "Le patient n'est pas hospitalisé"
    );
  }

  if (admission.bedId) {
    const bedIndex =
      beds.findIndex(
        (bed) =>
          bed.id ===
          admission.bedId
      );

    if (bedIndex !== -1) {
      beds[bedIndex] = {
        ...beds[bedIndex],
        occupiedByAdmissionId:
          undefined,
      };
    }
  }

  admissions[index] = {
    ...admission,

    status:
      "DISCHARGED",

    dischargeNotes:
      notes.trim(),

    dischargedAt:
      new Date().toISOString(),
  };

  saveAdmissions(admissions);
  saveBeds(beds);

  return admissions[index];
}
