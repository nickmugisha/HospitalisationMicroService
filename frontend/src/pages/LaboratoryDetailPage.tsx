import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Microscope,
  Printer,
  Plus,
  Save,
  TestTube2,
  Trash2,
} from "lucide-react";

import {
  useEffect,
  useState,
} from "react";

import {
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  collectSample,
  completeLaboratoryRequest,
  getLaboratoryRequest,
  saveLaboratoryTests,
  startAnalysis,
} from "../services/laboratoryService";

import {
  exportLaboratoryResultPdf,
  printLaboratoryResult,
} from "../services/documentService";

import type {
  LaboratoryRequest,
  LaboratoryTest,
} from "../types/laboratory";

export default function LaboratoryDetailPage() {
  const navigate =
    useNavigate();

  const { requestId } =
    useParams();

  const [request, setRequest] =
    useState<LaboratoryRequest | null>(
      null
    );

  const [loading, setLoading] =
    useState(true);

  async function load() {
    if (!requestId) {
      return;
    }

    setRequest(
      await getLaboratoryRequest(
        requestId
      )
    );

    setLoading(false);
  }

  useEffect(() => {
    load();
  }, [requestId]);

  function addTest() {
    if (!request) {
      return;
    }

    const test: LaboratoryTest = {
      id: crypto.randomUUID(),
      name: "",
      result: "",
      unit: "",
      referenceRange: "",
      abnormal: false,
    };

    setRequest({
      ...request,

      tests: [
        ...request.tests,
        test,
      ],
    });
  }

  function updateTest(
    id: string,
    field:
      keyof Omit<
        LaboratoryTest,
        "id"
      >,
    value: string | boolean
  ) {
    if (!request) {
      return;
    }

    setRequest({
      ...request,

      tests:
        request.tests.map(
          (test) =>
            test.id === id
              ? {
                  ...test,
                  [field]: value,
                }
              : test
        ),
    });
  }

  function removeTest(
    id: string
  ) {
    if (!request) {
      return;
    }

    setRequest({
      ...request,

      tests:
        request.tests.filter(
          (test) =>
            test.id !== id
        ),
    });
  }

  async function handleSave() {
    if (!request) {
      return;
    }

    setRequest(
      await saveLaboratoryTests(
        request.id,
        request.tests
      )
    );
  }

  async function handleCollect() {
    if (!request) {
      return;
    }

    setRequest(
      await collectSample(
        request.id
      )
    );
  }

  async function handleStart() {
    if (!request) {
      return;
    }

    setRequest(
      await startAnalysis(
        request.id
      )
    );
  }

  async function handleComplete() {
    if (!request) {
      return;
    }

    await handleSave();

    setRequest(
      await completeLaboratoryRequest(
        request.id
      )
    );
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement...
      </div>
    );
  }

  if (!request) {
    return (
      <div className="patient-detail-state">
        Demande introuvable.
      </div>
    );
  }

  return (
    <div className="laboratory-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate("/laboratoire")
        }
      >
        <ArrowLeft size={17} />
        Retour au laboratoire
      </button>

      <section className="medical-header">
        <div>
          <p className="eyebrow">
            DOSSIER LABORATOIRE
          </p>

          <h1>
            {request.patientName}
          </h1>

          <div className="profile-meta">
            <span>
              {request.patientNumber}
            </span>

            <span>
              {request.requestNotes}
            </span>
          </div>
        </div>

        <div className="medical-header-actions">
          {request.status === "COMPLETED" && (
            <>
              <button
                className="secondary-action medical-save"
                onClick={() =>
                  exportLaboratoryResultPdf(request)
                }
              >
                <Download size={16} />
                PDF
              </button>

              <button
                className="secondary-action medical-save"
                onClick={() =>
                  printLaboratoryResult(request)
                }
              >
                <Printer size={16} />
                Imprimer
              </button>
            </>
          )}

          {request.status ===
            "WAITING" && (
            <button
              className="secondary-action medical-save"
              onClick={
                handleCollect
              }
            >
              <TestTube2 size={16} />
              Prélèvement effectué
            </button>
          )}

          {request.status ===
            "SAMPLE_COLLECTED" && (
            <button
              className="secondary-action medical-save"
              onClick={
                handleStart
              }
            >
              <Microscope size={16} />
              Commencer analyse
            </button>
          )}

          <button
            className="secondary-action medical-save"
            onClick={handleSave}
          >
            <Save size={16} />
            Enregistrer
          </button>

          {request.status !==
            "COMPLETED" && (
            <button
              className="primary-action"
              onClick={
                handleComplete
              }
            >
              <CheckCircle2
                size={16}
              />
              Valider résultats
            </button>
          )}
        </div>
      </section>

      <section className="medical-card laboratory-request-info">
        <span className="section-label">
          PRESCRIPTION MÉDICALE
        </span>

        <h2>
          Analyses demandées
        </h2>

        <p>
          {request.requestNotes}
        </p>
      </section>

      <section className="medical-card laboratory-tests-card">
        <div className="section-header">
          <div>
            <span className="section-label">
              RÉSULTATS
            </span>

            <h2>
              Examens biologiques
            </h2>
          </div>

          <button
            className="secondary-action medical-save"
            onClick={addTest}
          >
            <Plus size={16} />
            Ajouter analyse
          </button>
        </div>

        <div className="laboratory-tests">
          {request.tests.map(
            (test) => (
              <div
                className="laboratory-test-row"
                key={test.id}
              >
                <input
                  value={test.name}
                  onChange={(event) =>
                    updateTest(
                      test.id,
                      "name",
                      event.target.value
                    )
                  }
                  placeholder="Analyse"
                />

                <input
                  value={test.result}
                  onChange={(event) =>
                    updateTest(
                      test.id,
                      "result",
                      event.target.value
                    )
                  }
                  placeholder="Résultat"
                />

                <input
                  value={test.unit}
                  onChange={(event) =>
                    updateTest(
                      test.id,
                      "unit",
                      event.target.value
                    )
                  }
                  placeholder="Unité"
                />

                <input
                  value={
                    test.referenceRange
                  }
                  onChange={(event) =>
                    updateTest(
                      test.id,
                      "referenceRange",
                      event.target.value
                    )
                  }
                  placeholder="Valeur normale"
                />

                <label className="abnormal-check">
                  <input
                    type="checkbox"
                    checked={
                      test.abnormal
                    }
                    onChange={(event) =>
                      updateTest(
                        test.id,
                        "abnormal",
                        event.target.checked
                      )
                    }
                  />

                  Anormal
                </label>

                <button
                  className="delete-prescription"
                  onClick={() =>
                    removeTest(test.id)
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            )
          )}

          {request.tests.length ===
            0 && (
            <div className="empty-history">
              Aucun résultat enregistré.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
