import type {
  CreatePatientInput,
  Patient,
  PatientHistoryEntry,
} from "../types/patient";

const STORAGE_KEY = "hospitalis_patients";

function createHistory(
  type: PatientHistoryEntry["type"],
  label: string,
  service?: string,
  note?: string
): PatientHistoryEntry {
  return {
    id: crypto.randomUUID(),
    type,
    label,
    service,
    note,
    at: new Date().toISOString(),
  };
}

const demoPatients: Patient[] = [
  {
    id: "patient-001",
    patientNumber: "PAT-2026-0001",
    firstName: "Aline",
    lastName: "Niyonkuru",
    sex: "F",
    birthDate: "1997-04-12",
    phone: "+257 79 10 20 30",
    email: "aline@example.com",
    address: "Bujumbura",
    emergencyContact:
      "Jean Niyonkuru - +257 71 20 30 40",
    status: "ACTIVE",
    arrivalStatus: "ORIENTED",
    arrivalReason: "Fièvre et fatigue",
    targetService: "Consultation",
    createdAt: new Date().toISOString(),
    history: [],
  },
  {
    id: "patient-002",
    patientNumber: "PAT-2026-0002",
    firstName: "Eric",
    lastName: "Ndayizeye",
    sex: "M",
    birthDate: "1988-09-22",
    phone: "+257 68 40 50 60",
    email: "eric@example.com",
    address: "Gitega",
    emergencyContact:
      "Claire - +257 79 44 33 22",
    status: "ACTIVE",
    arrivalStatus: "ORIENTED",
    arrivalReason: "Contrôle médical",
    targetService: "Consultation",
    createdAt: new Date().toISOString(),
    history: [],
  },
];

function normalizePatient(
  patient: Patient
): Patient {
  return {
    ...patient,
    history: patient.history ?? [],
  };
}

function loadPatients(): Patient[] {
  const stored =
    localStorage.getItem(STORAGE_KEY);

  if (!stored) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(demoPatients)
    );

    return demoPatients;
  }

  try {
    const parsed =
      JSON.parse(stored) as Patient[];

    return parsed.map(normalizePatient);
  } catch {
    return [];
  }
}

function savePatients(
  patients: Patient[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(patients)
  );
}

function generatePatientNumber(
  patients: Patient[]
) {
  const year =
    new Date().getFullYear();

  const maxNumber =
    patients.reduce(
      (max, patient) => {
        const parts =
          patient.patientNumber.split("-");

        const value =
          Number(parts.at(-1));

        return Number.isNaN(value)
          ? max
          : Math.max(max, value);
      },
      0
    );

  return `PAT-${year}-${String(
    maxNumber + 1
  ).padStart(4, "0")}`;
}

export async function listPatients():
  Promise<Patient[]> {
  return loadPatients();
}

export async function getPatientById(
  patientId: string
): Promise<Patient | null> {
  return (
    loadPatients().find(
      (patient) =>
        patient.id === patientId
    ) ?? null
  );
}

export async function createPatient(
  input: CreatePatientInput
): Promise<Patient> {
  const patients =
    loadPatients();

  const createdAt =
    new Date().toISOString();

  const patient: Patient = {
    id: crypto.randomUUID(),

    patientNumber:
      generatePatientNumber(patients),

    firstName:
      input.firstName.trim(),

    lastName:
      input.lastName.trim(),

    sex: input.sex,

    birthDate:
      input.birthDate,

    phone:
      input.phone.trim(),

    email:
      input.email?.trim(),

    address:
      input.address.trim(),

    emergencyContact:
      input.emergencyContact.trim(),

    status: "ACTIVE",

    arrivalStatus: "NONE",

    createdAt,

    history: [
      createHistory(
        "CREATED",
        "Dossier patient créé"
      ),
    ],
  };

  savePatients([
    patient,
    ...patients,
  ]);

  return patient;
}

export async function updatePatient(
  patientId: string,
  input: CreatePatientInput
): Promise<Patient> {
  const patients =
    loadPatients();

  const index =
    patients.findIndex(
      (patient) =>
        patient.id === patientId
    );

  if (index === -1) {
    throw new Error(
      "Patient introuvable"
    );
  }

  const current =
    patients[index];

  const updated: Patient = {
    ...current,

    firstName:
      input.firstName.trim(),

    lastName:
      input.lastName.trim(),

    sex: input.sex,

    birthDate:
      input.birthDate,

    phone:
      input.phone.trim(),

    email:
      input.email?.trim(),

    address:
      input.address.trim(),

    emergencyContact:
      input.emergencyContact.trim(),

    updatedAt:
      new Date().toISOString(),

    history: [
      createHistory(
        "UPDATED",
        "Informations administratives modifiées"
      ),
      ...(current.history ?? []),
    ],
  };

  patients[index] = updated;

  savePatients(patients);

  return updated;
}

export async function registerArrival(
  patientId: string,
  reason: string,
  targetService: string
): Promise<Patient> {
  const patients =
    loadPatients();

  const index =
    patients.findIndex(
      (patient) =>
        patient.id === patientId
    );

  if (index === -1) {
    throw new Error(
      "Patient introuvable"
    );
  }

  const current =
    patients[index];

  const updated: Patient = {
    ...current,

    arrivalStatus: "WAITING",

    arrivalReason:
      reason.trim(),

    targetService,

    updatedAt:
      new Date().toISOString(),

    history: [
      createHistory(
        "CHECK_IN",
        `Check-in vers ${targetService}`,
        targetService,
        reason.trim()
      ),
      ...(current.history ?? []),
    ],
  };

  patients[index] = updated;

  savePatients(patients);

  return updated;
}

export async function orientPatient(
  patientId: string
): Promise<Patient> {
  const patients =
    loadPatients();

  const index =
    patients.findIndex(
      (patient) =>
        patient.id === patientId
    );

  if (index === -1) {
    throw new Error(
      "Patient introuvable"
    );
  }

  const current =
    patients[index];

  const service =
    current.targetService ??
    "Service médical";

  const updated: Patient = {
    ...current,

    arrivalStatus: "ORIENTED",

    updatedAt:
      new Date().toISOString(),

    history: [
      createHistory(
        "ORIENTED",
        `Patient orienté vers ${service}`,
        service
      ),
      ...(current.history ?? []),
    ],
  };

  patients[index] = updated;

  savePatients(patients);

  return updated;
}

export async function sendPatientToService(
  patientId: string,
  service: string
): Promise<Patient> {
  const patients =
    loadPatients();

  const index =
    patients.findIndex(
      (patient) =>
        patient.id === patientId
    );

  if (index === -1) {
    throw new Error(
      "Patient introuvable"
    );
  }

  const current =
    patients[index];

  const updated: Patient = {
    ...current,

    arrivalStatus: "ORIENTED",

    targetService: service,

    updatedAt:
      new Date().toISOString(),

    history: [
      createHistory(
        "TRANSFER",
        `Patient envoyé vers ${service}`,
        service
      ),
      ...(current.history ?? []),
    ],
  };

  patients[index] = updated;

  savePatients(patients);

  return updated;
}
