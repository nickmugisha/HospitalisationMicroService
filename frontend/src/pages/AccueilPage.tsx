import {
  CheckCircle2,
  Clock3,
  Search,
  UserPlus,
  Users,
  X,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { useNavigate } from "react-router-dom";

import {
  createPatient,
  listPatients,
  orientPatient,
  registerArrival,
} from "../services/patientService";

import type {
  CreatePatientInput,
  Patient,
  PatientSex,
} from "../types/patient";

const initialForm: CreatePatientInput = {
  firstName: "",
  lastName: "",
  sex: "M",
  birthDate: "",
  phone: "",
  email: "",
  address: "",
  emergencyContact: "",
};

export default function AccueilPage() {
  const navigate = useNavigate();

  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");

  const [showCreateModal, setShowCreateModal] =
    useState(false);

  const [form, setForm] =
    useState<CreatePatientInput>({
      ...initialForm,
    });

  const [arrivalPatient, setArrivalPatient] =
    useState<Patient | null>(null);

  const [arrivalReason, setArrivalReason] =
    useState("");

  const [targetService, setTargetService] =
    useState("Consultation");

  async function refreshPatients() {
    const data = await listPatients();
    setPatients(data);
  }

  useEffect(() => {
    refreshPatients();
  }, []);

  const filteredPatients = useMemo(() => {
    const value = search
      .trim()
      .toLowerCase();

    if (!value) {
      return patients;
    }

    return patients.filter((patient) => {
      const searchable = [
        patient.patientNumber,
        patient.firstName,
        patient.lastName,
        patient.phone,
        patient.email ?? "",
        patient.address,
      ]
        .join(" ")
        .toLowerCase();

      return searchable.includes(value);
    });
  }, [patients, search]);

  const waitingPatients =
    patients.filter(
      (patient) =>
        patient.arrivalStatus === "WAITING"
    );

  const orientedPatients =
    patients.filter(
      (patient) =>
        patient.arrivalStatus === "ORIENTED"
    );

  async function handleCreate(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    await createPatient(form);

    setForm({
      ...initialForm,
    });

    setShowCreateModal(false);

    await refreshPatients();
  }

  async function handleArrival(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!arrivalPatient) {
      return;
    }

    if (!arrivalReason.trim()) {
      return;
    }

    await registerArrival(
      arrivalPatient.id,
      arrivalReason,
      targetService
    );

    setArrivalPatient(null);
    setArrivalReason("");
    setTargetService("Consultation");

    await refreshPatients();
  }

  async function handleOrient(
    patientId: string
  ) {
    await orientPatient(patientId);
    await refreshPatients();
  }

  return (
    <div className="accueil-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 01 • ACCUEIL
          </p>

          <h1>
            Accueil & patients
          </h1>

          <p className="subtitle">
            Enregistrement, identification,
            check-in et orientation du patient.
          </p>
        </div>

        <button
          className="primary-action"
          onClick={() =>
            setShowCreateModal(true)
          }
        >
          <UserPlus size={18} />
          Nouveau patient
        </button>
      </header>

      <section className="dashboard-stats accueil-stats">
        <article>
          <div className="stat-icon">
            <Users />
          </div>

          <div>
            <span>
              Patients enregistrés
            </span>
            <strong>
              {patients.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Clock3 />
          </div>

          <div>
            <span>
              En attente
            </span>
            <strong>
              {waitingPatients.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <CheckCircle2 />
          </div>

          <div>
            <span>
              Orientés
            </span>
            <strong>
              {orientedPatients.length}
            </strong>
          </div>
        </article>
      </section>

      <section className="patient-workspace">
        <article className="patient-list-panel">
          <div className="panel-heading">
            <div>
              <span className="section-label">
                REGISTRE PATIENT
              </span>

              <h2>
                Patients
              </h2>
            </div>

            <div className="patient-search">
              <Search size={17} />

              <input
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value
                  )
                }
                placeholder="Nom, numéro, téléphone..."
              />
            </div>
          </div>

          <div className="patient-table-wrapper">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Numéro</th>
                  <th>Sexe</th>
                  <th>Téléphone</th>
                  <th>Statut arrivée</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {filteredPatients.map(
                  (patient) => (
                    <tr key={patient.id}>
                      <td>
                        <div className="patient-name">
                          <div className="patient-avatar">
                            {patient.firstName
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <div>
                            <strong>
                              {patient.firstName}{" "}
                              {patient.lastName}
                            </strong>

                            <span>
                              {patient.address ||
                                "Adresse non renseignée"}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td>
                        <code>
                          {patient.patientNumber}
                        </code>
                      </td>

                      <td>
                        {patient.sex === "M"
                          ? "Masculin"
                          : "Féminin"}
                      </td>

                      <td>
                        {patient.phone || "—"}
                      </td>

                      <td>
                        <span
                          className={`arrival-badge ${patient.arrivalStatus.toLowerCase()}`}
                        >
                          {patient.arrivalStatus ===
                          "NONE"
                            ? "Pas arrivé"
                            : patient.arrivalStatus ===
                                "WAITING"
                              ? "En attente"
                              : "Orienté"}
                        </span>
                      </td>

                      <td>
                        <div className="table-actions">
                          <button
                            className="table-action"
                            onClick={() =>
                              navigate(
                                `/accueil/patients/${patient.id}`
                              )
                            }
                          >
                            Fiche
                          </button>

                          {patient.arrivalStatus ===
                          "WAITING" ? (
                            <button
                              className="table-action success"
                              onClick={() =>
                                handleOrient(
                                  patient.id
                                )
                              }
                            >
                              Orienter
                            </button>
                          ) : (
                            <button
                              className="table-action"
                              onClick={() =>
                                setArrivalPatient(
                                  patient
                                )
                              }
                            >
                              Check-in
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                )}

                {filteredPatients.length ===
                  0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="empty-table"
                    >
                      Aucun patient trouvé.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="waiting-panel">
          <div className="panel-heading simple">
            <div>
              <span className="section-label">
                TEMPS RÉEL
              </span>

              <h2>
                File d'attente
              </h2>
            </div>

            <span className="queue-count">
              {waitingPatients.length}
            </span>
          </div>

          <div className="queue-list">
            {waitingPatients.map(
              (patient, index) => (
                <div
                  className="queue-item"
                  key={patient.id}
                >
                  <div className="queue-position">
                    {index + 1}
                  </div>

                  <div>
                    <strong>
                      {patient.firstName}{" "}
                      {patient.lastName}
                    </strong>

                    <span>
                      {patient.targetService}
                    </span>

                    <small>
                      {patient.arrivalReason}
                    </small>
                  </div>
                </div>
              )
            )}

            {waitingPatients.length ===
              0 && (
              <div className="empty-queue">
                Aucun patient dans la
                file d'attente.
              </div>
            )}
          </div>
        </aside>
      </section>

      {showCreateModal && (
        <div className="modal-backdrop">
          <form
            className="patient-modal"
            onSubmit={handleCreate}
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  NOUVEAU DOSSIER
                </span>

                <h2>
                  Enregistrer un patient
                </h2>

                <p>
                  Création du dossier
                  administratif.
                </p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setShowCreateModal(
                    false
                  )
                }
              >
                <X size={20} />
              </button>
            </div>

            <div className="form-grid">
              <label>
                Prénom *
                <input
                  value={form.firstName}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      firstName:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Nom *
                <input
                  value={form.lastName}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      lastName:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Sexe *
                <select
                  value={form.sex}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      sex:
                        event.target
                          .value as PatientSex,
                    })
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
                Date de naissance *
                <input
                  type="date"
                  value={form.birthDate}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      birthDate:
                        event.target.value,
                    })
                  }
                  required
                />
              </label>

              <label>
                Téléphone
                <input
                  value={form.phone}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      phone:
                        event.target.value,
                    })
                  }
                  placeholder="+257..."
                />
              </label>

              <label>
                Email
                <input
                  type="email"
                  value={form.email ?? ""}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      email:
                        event.target.value,
                    })
                  }
                  placeholder="patient@email.com"
                />
              </label>

              <label>
                Adresse
                <input
                  value={form.address}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      address:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                Contact d'urgence
                <input
                  value={
                    form.emergencyContact
                  }
                  onChange={(event) =>
                    setForm({
                      ...form,
                      emergencyContact:
                        event.target.value,
                    })
                  }
                />
              </label>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setShowCreateModal(
                    false
                  )
                }
              >
                Annuler
              </button>

              <button
                type="submit"
                className="primary-action"
              >
                Enregistrer
              </button>
            </div>
          </form>
        </div>
      )}

      {arrivalPatient && (
        <div className="modal-backdrop">
          <form
            className="patient-modal compact-modal"
            onSubmit={handleArrival}
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  CHECK-IN
                </span>

                <h2>
                  Arrivée du patient
                </h2>

                <p>
                  {arrivalPatient.firstName}{" "}
                  {arrivalPatient.lastName}
                  {" • "}
                  {
                    arrivalPatient.patientNumber
                  }
                </p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setArrivalPatient(null)
                }
              >
                <X size={20} />
              </button>
            </div>

            <label className="modal-label">
              Motif de l'arrivée *

              <textarea
                value={arrivalReason}
                onChange={(event) =>
                  setArrivalReason(
                    event.target.value
                  )
                }
                placeholder="Décrivez brièvement le motif..."
                required
              />
            </label>

            <label className="modal-label">
              Service cible

              <select
                value={targetService}
                onChange={(event) =>
                  setTargetService(
                    event.target.value
                  )
                }
              >
                <option>
                  Consultation
                </option>

                <option>
                  Laboratoire
                </option>

                <option>
                  Hospitalisation
                </option>

                <option>
                  Maternité
                </option>

                <option>
                  Pharmacie
                </option>

                <option>
                  Urgences
                </option>
              </select>
            </label>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setArrivalPatient(null)
                }
              >
                Annuler
              </button>

              <button
                type="submit"
                className="primary-action"
              >
                Ajouter à la file
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
