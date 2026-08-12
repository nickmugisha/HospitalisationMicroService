export type LaboratoryStatus =
  | "WAITING"
  | "SAMPLE_COLLECTED"
  | "IN_ANALYSIS"
  | "COMPLETED";

export interface LaboratoryTest {
  id: string;
  name: string;
  result: string;
  unit: string;
  referenceRange: string;
  abnormal: boolean;
}

export interface LaboratoryRequest {
  id: string;

  consultationId: string;

  patientId: string;
  patientNumber: string;
  patientName: string;

  requestNotes: string;

  status: LaboratoryStatus;

  tests: LaboratoryTest[];

  requestedAt: string;
  sampleCollectedAt?: string;
  analysisStartedAt?: string;
  completedAt?: string;
}
