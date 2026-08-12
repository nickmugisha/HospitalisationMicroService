import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  PackageCheck,
  Pill,
  Printer,
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
  assignMedication,
  dispenseOrderItem,
  getMedicationStock,
  getPharmacyOrder,
  listMedications,
  listStockBatches,
  setRequestedQuantity,
} from "../services/pharmacyService";

import {
  exportPharmacyDeliveryPdf,
  printPharmacyDelivery,
} from "../services/documentService";

import type {
  Medication,
  PharmacyOrder,
  StockBatch,
} from "../types/pharmacy";

function formatMoney(
  amount: number
) {
  return `${new Intl.NumberFormat(
    "fr-FR"
  ).format(amount)} BIF`;
}

export default function PharmacyOrderDetailPage() {
  const navigate =
    useNavigate();

  const { orderId } =
    useParams();

  const [order, setOrder] =
    useState<PharmacyOrder | null>(
      null
    );

  const [
    medications,
    setMedications,
  ] =
    useState<Medication[]>([]);

  const [batches, setBatches] =
    useState<StockBatch[]>([]);

  const [
    requestedQuantities,
    setRequestedQuantities,
  ] = useState<
    Record<string, string>
  >({});

  const [
    dispenseQuantities,
    setDispenseQuantities,
  ] = useState<
    Record<string, string>
  >({});

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  async function load() {
    if (!orderId) {
      return;
    }

    const [
      orderData,
      medicationData,
      batchData,
    ] = await Promise.all([
      getPharmacyOrder(
        orderId
      ),
      listMedications(),
      listStockBatches(),
    ]);

    setOrder(orderData);

    setMedications(
      medicationData
    );

    setBatches(
      batchData
    );

    if (orderData) {
      const requested:
        Record<string, string> =
        {};

      const dispensing:
        Record<string, string> =
        {};

      for (
        const item
        of orderData.items
      ) {
        requested[
          item.id
        ] = String(
          item.requestedQuantity
        );

        dispensing[
          item.id
        ] = String(
          Math.max(
            item.requestedQuantity -
              item.dispensedQuantity,
            1
          )
        );
      }

      setRequestedQuantities(
        requested
      );

      setDispenseQuantities(
        dispensing
      );
    }

    setLoading(false);
  }

  useEffect(() => {
    load();
  }, [orderId]);

  async function handleMedication(
    itemId: string,
    medicationId: string
  ) {
    if (!order) {
      return;
    }

    setError("");

    try {
      const updated =
        await assignMedication(
          order.id,
          itemId,
          medicationId
        );

      setOrder(updated);
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur."
      );
    }
  }

  async function handleRequestedQuantity(
    itemId: string
  ) {
    if (!order) {
      return;
    }

    setError("");

    try {
      const updated =
        await setRequestedQuantity(
          order.id,
          itemId,
          Number(
            requestedQuantities[
              itemId
            ]
          )
        );

      setOrder(updated);
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Quantité invalide."
      );
    }
  }

  async function handleDispense(
    itemId: string
  ) {
    if (!order) {
      return;
    }

    setError("");

    try {
      const updated =
        await dispenseOrderItem(
          order.id,
          itemId,
          Number(
            dispenseQuantities[
              itemId
            ]
          )
        );

      setOrder(updated);

      setBatches(
        await listStockBatches()
      );

      const item =
        updated.items.find(
          (current) =>
            current.id ===
            itemId
        );

      if (item) {
        const remaining =
          item.requestedQuantity -
          item.dispensedQuantity;

        setDispenseQuantities(
          (current) => ({
            ...current,

            [itemId]:
              String(
                Math.max(
                  remaining,
                  1
                )
              ),
          })
        );
      }
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur pendant la délivrance."
      );
    }
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement de l'ordonnance...
      </div>
    );
  }

  if (!order) {
    return (
      <div className="patient-detail-state">
        Ordonnance introuvable.
      </div>
    );
  }

  return (
    <div className="pharmacy-order-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate("/pharmacie")
        }
      >
        <ArrowLeft size={17} />
        Retour à la pharmacie
      </button>

      <section className="medical-header">
        <div>
          <p className="eyebrow">
            ORDONNANCE PHARMACIE
          </p>

          <h1>
            {order.patientName}
          </h1>

          <div className="profile-meta">
            <span>
              {order.patientNumber}
            </span>

            <span>
              {
                order.items.length
              }{" "}
              médicament(s)
            </span>
          </div>
        </div>

        <div className="medical-header-actions">
          <span
            className={`pharmacy-status ${order.status.toLowerCase()}`}
          >
            {order.status ===
            "WAITING"
              ? "À délivrer"
              : order.status ===
                  "PARTIAL"
                ? "Partielle"
                : "Délivrée"}
          </span>

          {order.status ===
            "DISPENSED" && (
            <>
              <button
                className="secondary-action medical-save"
                onClick={() =>
                  exportPharmacyDeliveryPdf(
                    order,
                    medications
                  )
                }
              >
                <Download size={16} />
                Bon PDF
              </button>

              <button
                className="secondary-action medical-save"
                onClick={() =>
                  printPharmacyDelivery(
                    order,
                    medications
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
          <AlertTriangle
            size={17}
          />
          {error}
        </div>
      )}

      <section className="pharmacy-prescription-card">
        <div className="section-header">
          <div>
            <span className="section-label">
              PRESCRIPTION MÉDICALE
            </span>

            <h2>
              Médicaments à délivrer
            </h2>
          </div>

          <Pill />
        </div>

        <div className="pharmacy-prescription-list">
          {order.items.map(
            (item) => {
              const medication =
                medications.find(
                  (current) =>
                    current.id ===
                    item.medicationId
                );

              const stock =
                item.medicationId
                  ? getMedicationStock(
                      item.medicationId,
                      batches
                    )
                  : 0;

              const remaining =
                item.requestedQuantity -
                item.dispensedQuantity;

              const completed =
                remaining <= 0;

              return (
                <article
                  className="pharmacy-prescription-item"
                  key={item.id}
                >
                  <div className="pharmacy-prescribed">
                    <div className="pharmacy-med-icon">
                      <Pill />
                    </div>

                    <div>
                      <span>
                        PRESCRIT
                      </span>

                      <h3>
                        {item.prescribedName ||
                          "Médicament non renseigné"}
                      </h3>

                      <p>
                        {item.dosage ||
                          "Dosage —"}
                        {" • "}
                        {item.frequency ||
                          "Fréquence —"}
                        {" • "}
                        {item.duration ||
                          "Durée —"}
                      </p>
                    </div>
                  </div>

                  <div className="pharmacy-dispensing-grid">
                    <label>
                      Médicament du stock

                      <select
                        value={
                          item.medicationId ??
                          ""
                        }
                        disabled={
                          item.dispensedQuantity >
                          0
                        }
                        onChange={(event) =>
                          handleMedication(
                            item.id,
                            event.target.value
                          )
                        }
                      >
                        <option value="">
                          Sélectionner...
                        </option>

                        {medications.map(
                          (current) => (
                            <option
                              key={
                                current.id
                              }
                              value={
                                current.id
                              }
                            >
                              {
                                current.name
                              }
                              {" • "}
                              {
                                current.strength
                              }
                            </option>
                          )
                        )}
                      </select>
                    </label>

                    <label>
                      Quantité prescrite

                      <div className="pharmacy-inline-input">
                        <input
                          type="number"
                          min="1"
                          value={
                            requestedQuantities[
                              item.id
                            ] ?? "1"
                          }
                          disabled={
                            completed
                          }
                          onChange={(event) =>
                            setRequestedQuantities(
                              (current) => ({
                                ...current,
                                [item.id]:
                                  event
                                    .target
                                    .value,
                              })
                            )
                          }
                        />

                        <button
                          type="button"
                          disabled={
                            completed
                          }
                          onClick={() =>
                            handleRequestedQuantity(
                              item.id
                            )
                          }
                        >
                          OK
                        </button>
                      </div>
                    </label>

                    <div className="pharmacy-stock-info">
                      <span>
                        Stock disponible
                      </span>

                      <strong>
                        {medication
                          ? `${stock} ${medication.unit}(s)`
                          : "—"}
                      </strong>

                      {medication && (
                        <small>
                          {formatMoney(
                            medication.salePrice
                          )}
                          {" / "}
                          {
                            medication.unit
                          }
                        </small>
                      )}
                    </div>

                    <div className="pharmacy-stock-info">
                      <span>
                        Déjà délivré
                      </span>

                      <strong>
                        {
                          item.dispensedQuantity
                        }
                        {" / "}
                        {
                          item.requestedQuantity
                        }
                      </strong>
                    </div>
                  </div>

                  {!completed ? (
                    <div className="pharmacy-dispense-box">
                      <label>
                        Quantité à délivrer

                        <input
                          type="number"
                          min="1"
                          max={
                            remaining
                          }
                          value={
                            dispenseQuantities[
                              item.id
                            ] ?? "1"
                          }
                          onChange={(event) =>
                            setDispenseQuantities(
                              (current) => ({
                                ...current,
                                [item.id]:
                                  event
                                    .target
                                    .value,
                              })
                            )
                          }
                        />
                      </label>

                      <button
                        className="primary-action"
                        disabled={
                          !item.medicationId
                        }
                        onClick={() =>
                          handleDispense(
                            item.id
                          )
                        }
                      >
                        <PackageCheck
                          size={17}
                        />
                        Délivrer
                      </button>
                    </div>
                  ) : (
                    <div className="pharmacy-item-complete">
                      <CheckCircle2
                        size={18}
                      />
                      Médicament entièrement
                      délivré
                    </div>
                  )}
                </article>
              );
            }
          )}
        </div>
      </section>

      {order.status ===
        "DISPENSED" && (
        <section className="pharmacy-complete-card">
          <CheckCircle2 />

          <div>
            <span className="section-label">
              DÉLIVRANCE TERMINÉE
            </span>

            <h2>
              Ordonnance entièrement
              délivrée
            </h2>

            <p>
              Les stocks ont été
              déduits automatiquement
              selon FEFO et les
              médicaments ont été
              envoyés en facturation.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
