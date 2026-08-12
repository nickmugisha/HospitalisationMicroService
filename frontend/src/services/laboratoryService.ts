import type {
  LaboratoryRequest,
  LaboratoryTest,
} from "../types/laboratory";

import {
  listConsultations,
} from "./consultationService";

const STORAGE_KEY =
  "hospitalis_laboratory_requests";

function loadRequests():
  LaboratoryRequest[] {
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
    ) as LaboratoryRequest[];
  } catch {
    return [];
  }
}

function saveRequests(
  requests: LaboratoryRequest[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(requests)
  );
}

export async function synchronizeLaboratoryRequests():
  Promise<LaboratoryRequest[]> {
  const consultations =
    await listConsultations();

  const requests =
    loadRequests();

  let changed = false;

  for (const consultation of consultations) {
    if (
      !consultation.laboratoryRequested
    ) {
      continue;
    }

    const exists =
      requests.some(
        (request) =>
          request.consultationId ===
          consultation.id
      );

    if (exists) {
      continue;
    }

    requests.unshift({
      id: crypto.randomUUID(),

      consultationId:
        consultation.id,

      patientId:
        consultation.patientId,

      patientNumber:
        consultation.patientNumber,

      patientName:
        consultation.patientName,

      requestNotes:
        consultation.laboratoryNotes ??
        "Analyses médicales demandées",

      status: "WAITING",

      tests: [],

      requestedAt:
        new Date().toISOString(),
    });

    changed = true;
  }

  if (changed) {
    saveRequests(requests);
  }

  return requests;
}

export async function listLaboratoryRequests():
  Promise<LaboratoryRequest[]> {
  await synchronizeLaboratoryRequests();

  return loadRequests();
}

export async function getLaboratoryRequest(
  requestId: string
): Promise<LaboratoryRequest | null> {
  await synchronizeLaboratoryRequests();

  return (
    loadRequests().find(
      (request) =>
        request.id === requestId
    ) ?? null
  );
}

export async function collectSample(
  requestId: string
): Promise<LaboratoryRequest> {
  const requests =
    loadRequests();

  const index =
    requests.findIndex(
      (request) =>
        request.id === requestId
    );

  if (index === -1) {
    throw new Error(
      "Demande laboratoire introuvable"
    );
  }

  requests[index] = {
    ...requests[index],

    status: "SAMPLE_COLLECTED",

    sampleCollectedAt:
      new Date().toISOString(),
  };

  saveRequests(requests);

  return requests[index];
}

export async function startAnalysis(
  requestId: string
): Promise<LaboratoryRequest> {
  const requests =
    loadRequests();

  const index =
    requests.findIndex(
      (request) =>
        request.id === requestId
    );

  if (index === -1) {
    throw new Error(
      "Demande laboratoire introuvable"
    );
  }

  requests[index] = {
    ...requests[index],

    status: "IN_ANALYSIS",

    analysisStartedAt:
      new Date().toISOString(),
  };

  saveRequests(requests);

  return requests[index];
}

export async function saveLaboratoryTests(
  requestId: string,
  tests: LaboratoryTest[]
): Promise<LaboratoryRequest> {
  const requests =
    loadRequests();

  const index =
    requests.findIndex(
      (request) =>
        request.id === requestId
    );

  if (index === -1) {
    throw new Error(
      "Demande laboratoire introuvable"
    );
  }

  requests[index] = {
    ...requests[index],
    tests,
  };

  saveRequests(requests);

  return requests[index];
}

export async function completeLaboratoryRequest(
  requestId: string
): Promise<LaboratoryRequest> {
  const requests =
    loadRequests();

  const index =
    requests.findIndex(
      (request) =>
        request.id === requestId
    );

  if (index === -1) {
    throw new Error(
      "Demande laboratoire introuvable"
    );
  }

  requests[index] = {
    ...requests[index],

    status: "COMPLETED",

    completedAt:
      new Date().toISOString(),
  };

  saveRequests(requests);

  return requests[index];
}
