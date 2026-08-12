import {
  ArrowLeft,
  Baby,
  CheckCircle2,
  Download,
  HeartPulse,
  Hospital,
  Printer,
  Save,
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
  admitMaternityPatient,
  dischargeMaternityPatient,
  getMaternityCase,
  registerDelivery,
  saveMaternityInformation,
  startLabor,
} from "../services/maternityService";

import {
  exportMaternitySummaryPdf,
  printMaternitySummary,
} from "../services/documentService";

import type {
  DeliveryType,
  MaternityCase,
  NewbornSex,
} from "../types/maternity";

function formatDate(
  value?: string
) {
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

export default function MaternityDetailPage() {
  const navigate =
    useNavigate();

  const { caseId } =
    useParams();

  const [maternity, setMaternity] =
    useState<MaternityCase | null>(
      null
    );

  const [loading, setLoading] =
    useState(true);

  const [
    deliveryType,
    setDeliveryType,
  ] =
    useState<DeliveryType>(
      "VAGINAL"
    );

  const [
    deliveryNotes,
    setDeliveryNotes,
  ] = useState("");

  const [
    newbornName,
    setNewbornName,
  ] = useState("");

  const [
    newbornSex,
    setNewbornSex,
  ] =
    useState<NewbornSex>(
      "M"
    );

  const [
    newbornWeight,
    setNewbornWeight,
  ] = useState("");

  const [
    newbornLength,
    setNewbornLength,
  ] = useState("");

  const [apgar1, setApgar1] =
    useState("");

  const [apgar5, setApgar5] =
    useState("");

  const [
    newbornObservations,
    setNewbornObservations,
  ] = useState("");

  const [
    dischargeNotes,
    setDischargeNotes,
  ] = useState("");

  const [error, setError] =
    useState("");

  async function load() {
    if (!caseId) {
      return;
    }

    const result =
      await getMaternityCase(
        caseId
      );

    setMaternity(result);

    setLoading(false);
  }

  useEffect(() => {
    load();
  }, [caseId]);

  function updateField(
    field:
      | "gestationalAgeWeeks"
      | "gravida"
      | "para"
      | "bloodGroup"
      | "estimatedDueDate"
      | "riskNotes"
      | "admissionNotes",
    value: string
  ) {
    if (!maternity) {
      return;
    }

    setMaternity({
      ...maternity,
      [field]: value,
    });
  }

  async function handleSave() {
    if (!maternity) {
      return;
    }

    setError("");

    try {
      const updated =
        await saveMaternityInformation(
          maternity.id,
          {
            gestationalAgeWeeks:
              maternity.gestationalAgeWeeks,

            gravida:
              maternity.gravida,

            para:
              maternity.para,

            bloodGroup:
              maternity.bloodGroup,

            estimatedDueDate:
              maternity.estimatedDueDate,

            riskNotes:
              maternity.riskNotes,

            admissionNotes:
              maternity.admissionNotes,
          }
        );

      setMaternity(updated);
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur."
      );
    }
  }

  async function handleAdmit() {
    if (!maternity) {
      return;
    }

    await handleSave();

    try {
      setMaternity(
        await admitMaternityPatient(
          maternity.id
        )
      );
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur."
      );
    }
  }

  async function handleLabor() {
    if (!maternity) {
      return;
    }

    try {
      setMaternity(
        await startLabor(
          maternity.id
        )
      );
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur."
      );
    }
  }

  async function handleDelivery() {
    if (!maternity) {
      return;
    }

    setError("");

    try {
      setMaternity(
        await registerDelivery(
          maternity.id,
          {
            deliveryType,

            deliveryNotes,

            newbornName,

            newbornSex,

            newbornWeightGrams:
              Number(
                newbornWeight
              ),

            newbornLengthCm:
              Number(
                newbornLength
              ),

            apgar1:
              Number(apgar1),

            apgar5:
              Number(apgar5),

            newbornObservations,
          }
        )
      );
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur pendant l'accouchement."
      );
    }
  }

  async function handleDischarge() {
    if (!maternity) {
      return;
    }

    setError("");

    try {
      setMaternity(
        await dischargeMaternityPatient(
          maternity.id,
          dischargeNotes
        )
      );
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur pendant la sortie."
      );
    }
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement du dossier maternité...
      </div>
    );
  }

  if (!maternity) {
    return (
      <div className="patient-detail-state">
        Dossier maternité introuvable.
      </div>
    );
  }

  return (
    <div className="maternity-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate("/maternite")
        }
      >
        <ArrowLeft size={17} />
        Retour à la maternité
      </button>

      <section className="medical-header maternity-header">
        <div>
          <p className="eyebrow">
            DOSSIER OBSTÉTRICAL
          </p>

          <h1>
            {maternity.patientName}
          </h1>

          <div className="profile-meta">
            <span>
              {
                maternity.patientNumber
              }
            </span>

            <span>
              {maternity.reason}
            </span>
          </div>
        </div>

        <div className="medical-header-actions">
          <span
            className={`maternity-status ${maternity.status.toLowerCase()}`}
          >
            {maternity.status ===
            "WAITING"
              ? "En attente"
              : maternity.status ===
                  "ADMITTED"
                ? "Admise"
                : maternity.status ===
                    "IN_LABOR"
                  ? "En travail"
                  : maternity.status ===
                      "DELIVERED"
                    ? "Accouchée"
                    : "Sortie"}
          </span>

          <button
            className="secondary-action medical-save"
            onClick={
              handleSave
            }
          >
            <Save size={16} />
            Enregistrer
          </button>

          {(maternity.status ===
            "DELIVERED" ||
            maternity.status ===
              "DISCHARGED") && (
            <>
              <button
                className="secondary-action medical-save"
                onClick={() =>
                  exportMaternitySummaryPdf(
                    maternity
                  )
                }
              >
                <Download size={16} />
                PDF
              </button>

              <button
                className="secondary-action medical-save"
                onClick={() =>
                  printMaternitySummary(
                    maternity
                  )
                }
              >
                <Printer size={16} />
                Imprimer
              </button>
            </>
          )}
        </div>
      </section>

      {error && (
        <div className="pharmacy-error">
          {error}
        </div>
      )}

      <section className="maternity-grid">
        <article className="medical-card">
          <span className="section-label">
            GROSSESSE
          </span>

          <h2>
            Informations obstétricales
          </h2>

          <div className="vitals-grid">
            <label>
              Âge gestationnel
              <input
                value={
                  maternity.gestationalAgeWeeks
                }
                onChange={(event) =>
                  updateField(
                    "gestationalAgeWeeks",
                    event.target.value
                  )
                }
                placeholder="38"
              />
            </label>

            <label>
              Date prévue d'accouchement
              <input
                type="date"
                value={
                  maternity.estimatedDueDate
                }
                onChange={(event) =>
                  updateField(
                    "estimatedDueDate",
                    event.target.value
                  )
                }
              />
            </label>

            <label>
              Gravida
              <input
                value={
                  maternity.gravida
                }
                onChange={(event) =>
                  updateField(
                    "gravida",
                    event.target.value
                  )
                }
                placeholder="G2"
              />
            </label>

            <label>
              Para
              <input
                value={
                  maternity.para
                }
                onChange={(event) =>
                  updateField(
                    "para",
                    event.target.value
                  )
                }
                placeholder="P1"
              />
            </label>

            <label>
              Groupe sanguin
              <input
                value={
                  maternity.bloodGroup
                }
                onChange={(event) =>
                  updateField(
                    "bloodGroup",
                    event.target.value
                  )
                }
                placeholder="O+"
              />
            </label>
          </div>

          <label className="medical-label">
            Facteurs de risque

            <textarea
              value={
                maternity.riskNotes
              }
              onChange={(event) =>
                updateField(
                  "riskNotes",
                  event.target.value
                )
              }
              placeholder="HTA, diabète gestationnel, antécédents..."
            />
          </label>
        </article>

        <article className="medical-card">
          <span className="section-label">
            PRISE EN CHARGE
          </span>

          <h2>
            Admission maternité
          </h2>

          <div className="hospital-info-list">
            <div>
              <span>
                Demande
              </span>

              <strong>
                {formatDate(
                  maternity.requestedAt
                )}
              </strong>
            </div>

            <div>
              <span>
                Admission
              </span>

              <strong>
                {formatDate(
                  maternity.admittedAt
                )}
              </strong>
            </div>

            <div>
              <span>
                Début du travail
              </span>

              <strong>
                {formatDate(
                  maternity.laborStartedAt
                )}
              </strong>
            </div>
          </div>

          <label className="medical-label">
            Notes d'admission

            <textarea
              value={
                maternity.admissionNotes
              }
              onChange={(event) =>
                updateField(
                  "admissionNotes",
                  event.target.value
                )
              }
              placeholder="État clinique à l'admission..."
            />
          </label>

          {maternity.status ===
            "WAITING" && (
            <button
              className="primary-action maternity-main-action"
              onClick={
                handleAdmit
              }
            >
              <Hospital size={17} />
              Admettre en maternité
            </button>
          )}

          {maternity.status ===
            "ADMITTED" && (
            <button
              className="primary-action maternity-main-action"
              onClick={
                handleLabor
              }
            >
              <HeartPulse
                size={17}
              />
              Débuter le travail
            </button>
          )}
        </article>
      </section>

      {maternity.status ===
        "IN_LABOR" && (
        <section className="medical-card maternity-delivery-card">
          <div className="section-header">
            <div>
              <span className="section-label">
                ACCOUCHEMENT
              </span>

              <h2>
                Enregistrer la naissance
              </h2>
            </div>

            <Baby />
          </div>

          <div className="maternity-delivery-grid">
            <label>
              Type d'accouchement

              <select
                value={
                  deliveryType
                }
                onChange={(event) =>
                  setDeliveryType(
                    event.target
                      .value as DeliveryType
                  )
                }
              >
                <option value="VAGINAL">
                  Voie basse
                </option>

                <option value="CESAREAN">
                  Césarienne
                </option>

                <option value="ASSISTED">
                  Accouchement assisté
                </option>
              </select>
            </label>

            <label>
              Nom du nouveau-né

              <input
                value={
                  newbornName
                }
                onChange={(event) =>
                  setNewbornName(
                    event.target.value
                  )
                }
                placeholder="Nom provisoire ou définitif"
              />
            </label>

            <label>
              Sexe du nouveau-né

              <select
                value={
                  newbornSex
                }
                onChange={(event) =>
                  setNewbornSex(
                    event.target
                      .value as NewbornSex
                  )
                }
              >
                <option value="M">
                  Masculin
                </option>

                <option value="F">
                  Féminin
                </option>
              </select>
            </label>

            <label>
              Poids en grammes

              <input
                type="number"
                min="1"
                value={
                  newbornWeight
                }
                onChange={(event) =>
                  setNewbornWeight(
                    event.target.value
                  )
                }
                placeholder="3200"
              />
            </label>

            <label>
              Taille en cm

              <input
                type="number"
                min="1"
                value={
                  newbornLength
                }
                onChange={(event) =>
                  setNewbornLength(
                    event.target.value
                  )
                }
                placeholder="50"
              />
            </label>

            <label>
              APGAR à 1 minute

              <input
                type="number"
                min="0"
                max="10"
                value={apgar1}
                onChange={(event) =>
                  setApgar1(
                    event.target.value
                  )
                }
                placeholder="8"
              />
            </label>

            <label>
              APGAR à 5 minutes

              <input
                type="number"
                min="0"
                max="10"
                value={apgar5}
                onChange={(event) =>
                  setApgar5(
                    event.target.value
                  )
                }
                placeholder="10"
              />
            </label>
          </div>

          <label className="medical-label">
            Notes sur l'accouchement

            <textarea
              value={
                deliveryNotes
              }
              onChange={(event) =>
                setDeliveryNotes(
                  event.target.value
                )
              }
              placeholder="Déroulement, complications éventuelles..."
            />
          </label>

          <label className="medical-label">
            Observations nouveau-né

            <textarea
              value={
                newbornObservations
              }
              onChange={(event) =>
                setNewbornObservations(
                  event.target.value
                )
              }
              placeholder="État du nouveau-né..."
            />
          </label>

          <button
            className="primary-action maternity-delivery-button"
            onClick={
              handleDelivery
            }
          >
            <Baby size={17} />
            Enregistrer l'accouchement
          </button>
        </section>
      )}

      {maternity.newborn && (
        <section className="newborn-card">
          <div className="newborn-icon">
            <Baby />
          </div>

          <div>
            <span className="section-label">
              NOUVEAU-NÉ
            </span>

            <h2>
              {maternity.newborn.name ||
                "Nouveau-né"}
            </h2>

            <div className="newborn-stats">
              <span>
                {maternity.newborn.sex ===
                "M"
                  ? "Masculin"
                  : "Féminin"}
              </span>

              <span>
                {
                  maternity.newborn
                    .weightGrams
                }{" "}
                g
              </span>

              <span>
                {
                  maternity.newborn
                    .lengthCm
                }{" "}
                cm
              </span>

              <span>
                APGAR 1' :{" "}
                {
                  maternity.newborn
                    .apgar1
                }
              </span>

              <span>
                APGAR 5' :{" "}
                {
                  maternity.newborn
                    .apgar5
                }
              </span>
            </div>

            <p>
              {maternity.newborn
                .observations ||
                "Aucune observation particulière."}
            </p>
          </div>
        </section>
      )}

      {maternity.status ===
        "DELIVERED" && (
        <section className="medical-card maternity-discharge-card">
          <span className="section-label">
            SORTIE MÈRE / ENFANT
          </span>

          <h2>
            Autoriser la sortie
          </h2>

          <label className="medical-label">
            Recommandations de sortie

            <textarea
              value={
                dischargeNotes
              }
              onChange={(event) =>
                setDischargeNotes(
                  event.target.value
                )
              }
              placeholder="Traitement, allaitement, rendez-vous de contrôle..."
            />
          </label>

          <button
            className="primary-action"
            onClick={
              handleDischarge
            }
          >
            <CheckCircle2
              size={17}
            />
            Enregistrer la sortie
          </button>
        </section>
      )}

      {maternity.status ===
        "DISCHARGED" && (
        <section className="pharmacy-complete-card">
          <CheckCircle2 />

          <div>
            <span className="section-label">
              DOSSIER CLÔTURÉ
            </span>

            <h2>
              Sortie mère/enfant
              enregistrée
            </h2>

            <p>
              {maternity.dischargeNotes ||
                "Aucune recommandation enregistrée."}
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
