import {
  ArrowLeft,
  CheckCircle2,
  FlaskConical,
  Hospital,
  Plus,
  Save,
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
  completeConsultation,
  getConsultationById,
  requestHospitalization,
  requestLaboratory,
  saveMedicalConsultation,
} from "../services/consultationService";

import type {
  Consultation,
  PrescriptionItem,
} from "../types/consultation";

export default function ConsultationDetailPage() {
  const navigate =
    useNavigate();

  const { consultationId } =
    useParams();

  const [consultation, setConsultation] =
    useState<Consultation | null>(
      null
    );

  const [loading, setLoading] =
    useState(true);

  const [laboratoryNotes, setLaboratoryNotes] =
    useState("");

  const [
    hospitalizationReason,
    setHospitalizationReason,
  ] = useState("");

  async function load() {
    if (!consultationId) {
      return;
    }

    const result =
      await getConsultationById(
        consultationId
      );

    setConsultation(result);

    if (result) {
      setLaboratoryNotes(
        result.laboratoryNotes ?? ""
      );

      setHospitalizationReason(
        result.hospitalizationReason ??
          ""
      );
    }

    setLoading(false);
  }

  useEffect(() => {
    load();
  }, [consultationId]);

  function updateField(
    field:
      | "symptoms"
      | "diagnosis"
      | "clinicalNotes",
    value: string
  ) {
    if (!consultation) {
      return;
    }

    setConsultation({
      ...consultation,
      [field]: value,
    });
  }

  function updateVital(
    field:
      keyof Consultation["vitalSigns"],
    value: string
  ) {
    if (!consultation) {
      return;
    }

    setConsultation({
      ...consultation,

      vitalSigns: {
        ...consultation.vitalSigns,
        [field]: value,
      },
    });
  }

  function addPrescription() {
    if (!consultation) {
      return;
    }

    const item: PrescriptionItem = {
      id: crypto.randomUUID(),
      medicine: "",
      dosage: "",
      frequency: "",
      duration: "",
    };

    setConsultation({
      ...consultation,

      prescriptions: [
        ...consultation.prescriptions,
        item,
      ],
    });
  }

  function updatePrescription(
    id: string,
    field:
      keyof Omit<
        PrescriptionItem,
        "id"
      >,
    value: string
  ) {
    if (!consultation) {
      return;
    }

    setConsultation({
      ...consultation,

      prescriptions:
        consultation.prescriptions.map(
          (item) =>
            item.id === id
              ? {
                  ...item,
                  [field]: value,
                }
              : item
        ),
    });
  }

  function removePrescription(
    id: string
  ) {
    if (!consultation) {
      return;
    }

    setConsultation({
      ...consultation,

      prescriptions:
        consultation.prescriptions.filter(
          (item) =>
            item.id !== id
        ),
    });
  }

  async function handleSave() {
    if (!consultation) {
      return;
    }

    const updated =
      await saveMedicalConsultation(
        consultation.id,
        {
          symptoms:
            consultation.symptoms,

          diagnosis:
            consultation.diagnosis,

          clinicalNotes:
            consultation.clinicalNotes,

          vitalSigns:
            consultation.vitalSigns,

          prescriptions:
            consultation.prescriptions,
        }
      );

    setConsultation(updated);
  }

  async function handleLaboratory() {
    if (!consultation) {
      return;
    }

    const updated =
      await requestLaboratory(
        consultation.id,
        laboratoryNotes
      );

    setConsultation(updated);
  }

  async function handleHospitalization() {
    if (
      !consultation ||
      !hospitalizationReason.trim()
    ) {
      return;
    }

    const updated =
      await requestHospitalization(
        consultation.id,
        hospitalizationReason
      );

    setConsultation(updated);
  }

  async function handleComplete() {
    if (!consultation) {
      return;
    }

    await handleSave();

    const updated =
      await completeConsultation(
        consultation.id
      );

    setConsultation(updated);
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement de la consultation...
      </div>
    );
  }

  if (!consultation) {
    return (
      <div className="patient-detail-state">
        <h2>
          Consultation introuvable
        </h2>

        <button
          className="primary-action"
          onClick={() =>
            navigate("/consultation")
          }
        >
          Retour
        </button>
      </div>
    );
  }

  return (
    <div className="consultation-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate("/consultation")
        }
      >
        <ArrowLeft size={17} />
        Retour à la file médicale
      </button>

      <section className="medical-header">
        <div>
          <p className="eyebrow">
            DOSSIER DE CONSULTATION
          </p>

          <h1>
            {consultation.patientName}
          </h1>

          <div className="profile-meta">
            <span>
              {
                consultation.patientNumber
              }
            </span>

            <span>
              {consultation.reason}
            </span>
          </div>
        </div>

        <div className="medical-header-actions">
          <span
            className={`consultation-status ${consultation.status.toLowerCase()}`}
          >
            {consultation.status ===
            "WAITING"
              ? "En attente"
              : consultation.status ===
                  "IN_PROGRESS"
                ? "En cours"
                : "Terminée"}
          </span>

          <button
            className="secondary-action medical-save"
            onClick={handleSave}
          >
            <Save size={16} />
            Enregistrer
          </button>

          {consultation.status !==
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
              Terminer
            </button>
          )}
        </div>
      </section>

      <section className="medical-grid">
        <article className="medical-card">
          <span className="section-label">
            CONSTANTES VITALES
          </span>

          <h2>
            Examen initial
          </h2>

          <div className="vitals-grid">
            <label>
              Température °C
              <input
                value={
                  consultation
                    .vitalSigns
                    .temperature
                }
                onChange={(event) =>
                  updateVital(
                    "temperature",
                    event.target.value
                  )
                }
                placeholder="36.8"
              />
            </label>

            <label>
              Tension artérielle
              <input
                value={
                  consultation
                    .vitalSigns
                    .bloodPressure
                }
                onChange={(event) =>
                  updateVital(
                    "bloodPressure",
                    event.target.value
                  )
                }
                placeholder="120/80"
              />
            </label>

            <label>
              Pouls / min
              <input
                value={
                  consultation
                    .vitalSigns
                    .heartRate
                }
                onChange={(event) =>
                  updateVital(
                    "heartRate",
                    event.target.value
                  )
                }
                placeholder="72"
              />
            </label>

            <label>
              SpO₂ %
              <input
                value={
                  consultation
                    .vitalSigns
                    .oxygenSaturation
                }
                onChange={(event) =>
                  updateVital(
                    "oxygenSaturation",
                    event.target.value
                  )
                }
                placeholder="98"
              />
            </label>

            <label>
              Poids kg
              <input
                value={
                  consultation
                    .vitalSigns
                    .weight
                }
                onChange={(event) =>
                  updateVital(
                    "weight",
                    event.target.value
                  )
                }
                placeholder="70"
              />
            </label>

            <label>
              Taille cm
              <input
                value={
                  consultation
                    .vitalSigns
                    .height
                }
                onChange={(event) =>
                  updateVital(
                    "height",
                    event.target.value
                  )
                }
                placeholder="175"
              />
            </label>
          </div>
        </article>

        <article className="medical-card">
          <span className="section-label">
            EXAMEN CLINIQUE
          </span>

          <h2>
            Observations
          </h2>

          <label className="medical-label">
            Symptômes
            <textarea
              value={
                consultation.symptoms
              }
              onChange={(event) =>
                updateField(
                  "symptoms",
                  event.target.value
                )
              }
              placeholder="Décrire les symptômes..."
            />
          </label>

          <label className="medical-label">
            Diagnostic
            <textarea
              value={
                consultation.diagnosis
              }
              onChange={(event) =>
                updateField(
                  "diagnosis",
                  event.target.value
                )
              }
              placeholder="Diagnostic médical..."
            />
          </label>

          <label className="medical-label">
            Notes cliniques
            <textarea
              value={
                consultation.clinicalNotes
              }
              onChange={(event) =>
                updateField(
                  "clinicalNotes",
                  event.target.value
                )
              }
              placeholder="Observations complémentaires..."
            />
          </label>
        </article>
      </section>

      <section className="medical-card prescription-card">
        <div className="section-header">
          <div>
            <span className="section-label">
              ORDONNANCE
            </span>

            <h2>
              Prescription médicale
            </h2>
          </div>

          <button
            className="secondary-action"
            onClick={
              addPrescription
            }
          >
            <Plus size={16} />
            Médicament
          </button>
        </div>

        <div className="prescription-list">
          {consultation.prescriptions.map(
            (item) => (
              <div
                className="prescription-row"
                key={item.id}
              >
                <input
                  value={
                    item.medicine
                  }
                  onChange={(event) =>
                    updatePrescription(
                      item.id,
                      "medicine",
                      event.target.value
                    )
                  }
                  placeholder="Médicament"
                />

                <input
                  value={
                    item.dosage
                  }
                  onChange={(event) =>
                    updatePrescription(
                      item.id,
                      "dosage",
                      event.target.value
                    )
                  }
                  placeholder="Dosage"
                />

                <input
                  value={
                    item.frequency
                  }
                  onChange={(event) =>
                    updatePrescription(
                      item.id,
                      "frequency",
                      event.target.value
                    )
                  }
                  placeholder="Fréquence"
                />

                <input
                  value={
                    item.duration
                  }
                  onChange={(event) =>
                    updatePrescription(
                      item.id,
                      "duration",
                      event.target.value
                    )
                  }
                  placeholder="Durée"
                />

                <button
                  onClick={() =>
                    removePrescription(
                      item.id
                    )
                  }
                  className="delete-prescription"
                  type="button"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            )
          )}

          {consultation.prescriptions
            .length === 0 && (
            <div className="empty-history">
              Aucun médicament prescrit.
            </div>
          )}
        </div>
      </section>

      <section className="clinical-decisions">
        <article className="decision-card">
          <div className="decision-icon">
            <FlaskConical />
          </div>

          <div>
            <span className="section-label">
              LABORATOIRE
            </span>

            <h2>
              Demande d'analyses
            </h2>

            <textarea
              value={laboratoryNotes}
              onChange={(event) =>
                setLaboratoryNotes(
                  event.target.value
                )
              }
              placeholder="Analyses demandées : NFS, glycémie..."
            />

            <button
              className="secondary-action"
              onClick={
                handleLaboratory
              }
            >
              <FlaskConical
                size={16}
              />

              {consultation
                .laboratoryRequested
                ? "Demande enregistrée"
                : "Envoyer au laboratoire"}
            </button>
          </div>
        </article>

        <article className="decision-card">
          <div className="decision-icon">
            <Hospital />
          </div>

          <div>
            <span className="section-label">
              HOSPITALISATION
            </span>

            <h2>
              Décision d'admission
            </h2>

            <textarea
              value={
                hospitalizationReason
              }
              onChange={(event) =>
                setHospitalizationReason(
                  event.target.value
                )
              }
              placeholder="Motif d'hospitalisation..."
            />

            <button
              className="secondary-action"
              onClick={
                handleHospitalization
              }
            >
              <Hospital size={16} />

              {consultation
                .hospitalizationRequested
                ? "Admission demandée"
                : "Demander hospitalisation"}
            </button>
          </div>
        </article>
      </section>
    </div>
  );
}
