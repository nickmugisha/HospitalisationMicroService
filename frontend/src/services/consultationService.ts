import type {
  Consultation,
  PrescriptionItem,
  VitalSigns,
} from "../types/consultation";

import {
  listPatients,
  sendPatientToService,
} from "./patientService";

const STORAGE_KEY =
  "hospitalis_consultations";

function loadConsultations():
  Consultation[] {
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
    ) as Consultation[];
  } catch {
    return [];
  }
}

function saveConsultations(
  consultations: Consultation[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(
      consultations
    )
  );
}

export async function synchronizeConsultationQueue():
  Promise<Consultation[]> {
  const patients =
    await listPatients();

  const consultations =
    loadConsultations();

  let changed = false;

  for (const patient of patients) {
    if (
      patient.targetService !==
        "Consultation" ||
      patient.arrivalStatus !==
        "ORIENTED"
    ) {
      continue;
    }

    const exists =
      consultations.some(
        (consultation) =>
          consultation.patientId ===
            patient.id &&
          consultation.status !==
            "COMPLETED"
      );

    if (exists) {
      continue;
    }

    consultations.push({
      id: crypto.randomUUID(),

      patientId:
        patient.id,

      patientNumber:
        patient.patientNumber,

      patientName:
        `${patient.firstName} ${patient.lastName}`,

      status: "WAITING",

      reason:
        patient.arrivalReason ??
        "Consultation médicale",

      symptoms: "",
      diagnosis: "",
      clinicalNotes: "",

      vitalSigns: {
        temperature: "",
        bloodPressure: "",
        heartRate: "",
        weight: "",
        height: "",
        oxygenSaturation: "",
      },

      prescriptions: [],

      laboratoryRequested:
        false,

      hospitalizationRequested:
        false,

      createdAt:
        new Date().toISOString(),
    });

    changed = true;
  }

  if (changed) {
    saveConsultations(
      consultations
    );
  }

  return consultations;
}

export async function listConsultations():
  Promise<Consultation[]> {
  await synchronizeConsultationQueue();

  return loadConsultations();
}

export async function getConsultationById(
  consultationId: string
): Promise<Consultation | null> {
  await synchronizeConsultationQueue();

  return (
    loadConsultations().find(
      (consultation) =>
        consultation.id ===
        consultationId
    ) ?? null
  );
}

export async function startConsultation(
  consultationId: string
): Promise<Consultation> {
  const consultations =
    loadConsultations();

  const index =
    consultations.findIndex(
      (consultation) =>
        consultation.id ===
        consultationId
    );

  if (index === -1) {
    throw new Error(
      "Consultation introuvable"
    );
  }

  consultations[index] = {
    ...consultations[index],

    status:
      "IN_PROGRESS",

    startedAt:
      consultations[index]
        .startedAt ??
      new Date().toISOString(),
  };

  saveConsultations(
    consultations
  );

  return consultations[index];
}

export async function saveMedicalConsultation(
  consultationId: string,
  data: {
    symptoms: string;
    diagnosis: string;
    clinicalNotes: string;
    vitalSigns: VitalSigns;
    prescriptions: PrescriptionItem[];
  }
): Promise<Consultation> {
  const consultations =
    loadConsultations();

  const index =
    consultations.findIndex(
      (consultation) =>
        consultation.id ===
        consultationId
    );

  if (index === -1) {
    throw new Error(
      "Consultation introuvable"
    );
  }

  consultations[index] = {
    ...consultations[index],
    ...data,
  };

  saveConsultations(
    consultations
  );

  return consultations[index];
}

export async function requestLaboratory(
  consultationId: string,
  notes: string
): Promise<Consultation> {
  const consultations =
    loadConsultations();

  const index =
    consultations.findIndex(
      (consultation) =>
        consultation.id ===
        consultationId
    );

  if (index === -1) {
    throw new Error(
      "Consultation introuvable"
    );
  }

  consultations[index] = {
    ...consultations[index],

    laboratoryRequested:
      true,

    laboratoryNotes:
      notes.trim(),
  };

  saveConsultations(
    consultations
  );

  await sendPatientToService(
    consultations[index].patientId,
    "Laboratoire"
  );

  return consultations[index];
}

export async function requestHospitalization(
  consultationId: string,
  reason: string
): Promise<Consultation> {
  const consultations =
    loadConsultations();

  const index =
    consultations.findIndex(
      (consultation) =>
        consultation.id ===
        consultationId
    );

  if (index === -1) {
    throw new Error(
      "Consultation introuvable"
    );
  }

  consultations[index] = {
    ...consultations[index],

    hospitalizationRequested:
      true,

    hospitalizationReason:
      reason.trim(),
  };

  saveConsultations(
    consultations
  );

  await sendPatientToService(
    consultations[index].patientId,
    "Hospitalisation"
  );

  return consultations[index];
}

export async function completeConsultation(
  consultationId: string
): Promise<Consultation> {
  const consultations =
    loadConsultations();

  const index =
    consultations.findIndex(
      (consultation) =>
        consultation.id ===
        consultationId
    );

  if (index === -1) {
    throw new Error(
      "Consultation introuvable"
    );
  }

  consultations[index] = {
    ...consultations[index],

    status:
      "COMPLETED",

    completedAt:
      new Date().toISOString(),
  };

  saveConsultations(
    consultations
  );

  return consultations[index];
}
