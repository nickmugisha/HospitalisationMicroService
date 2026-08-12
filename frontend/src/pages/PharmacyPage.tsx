import {
  AlertTriangle,
  Boxes,
  ClipboardList,
  History,
  PackagePlus,
  Pill,
  Search,
  Truck,
  X,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  getExpiringBatches,
  getLowStockMedications,
  getMedicationStock,
  listMedications,
  listPharmacyOrders,
  listStockBatches,
  listStockMovements,
  receiveStock,
} from "../services/pharmacyService";

import type {
  Medication,
  PharmacyOrder,
  StockBatch,
  StockMovement,
} from "../types/pharmacy";

type PharmacyTab =
  | "ORDERS"
  | "STOCK"
  | "MOVEMENTS";

function formatMoney(
  amount: number
) {
  return `${new Intl.NumberFormat(
    "fr-FR"
  ).format(amount)} BIF`;
}

function formatDate(
  value: string
) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      dateStyle: "medium",
      timeStyle: "short",
    }
  ).format(new Date(value));
}

function orderStatusLabel(
  status: PharmacyOrder["status"]
) {
  if (status === "WAITING") {
    return "À délivrer";
  }

  if (status === "PARTIAL") {
    return "Partielle";
  }

  return "Délivrée";
}

function movementLabel(
  type: StockMovement["type"]
) {
  if (type === "RECEIVE") {
    return "Entrée";
  }

  if (type === "DISPENSE") {
    return "Sortie";
  }

  return "Ajustement";
}

export default function PharmacyPage() {
  const navigate =
    useNavigate();

  const [tab, setTab] =
    useState<PharmacyTab>(
      "ORDERS"
    );

  const [orders, setOrders] =
    useState<PharmacyOrder[]>([]);

  const [
    medications,
    setMedications,
  ] =
    useState<Medication[]>([]);

  const [batches, setBatches] =
    useState<StockBatch[]>([]);

  const [
    movements,
    setMovements,
  ] =
    useState<StockMovement[]>([]);

  const [lowStock, setLowStock] =
    useState(0);

  const [
    expiringBatches,
    setExpiringBatches,
  ] =
    useState(0);

  const [search, setSearch] =
    useState("");

  const [
    showReceiveModal,
    setShowReceiveModal,
  ] = useState(false);

  const [
    receiveMedicationId,
    setReceiveMedicationId,
  ] = useState("");

  const [
    receiveBatchNumber,
    setReceiveBatchNumber,
  ] = useState("");

  const [
    receiveExpiry,
    setReceiveExpiry,
  ] = useState("");

  const [
    receiveQuantity,
    setReceiveQuantity,
  ] = useState("");

  const [error, setError] =
    useState("");

  async function refresh() {
    const [
      orderData,
      medicationData,
      batchData,
      movementData,
      lowStockData,
      expiryData,
    ] = await Promise.all([
      listPharmacyOrders(),
      listMedications(),
      listStockBatches(),
      listStockMovements(),
      getLowStockMedications(),
      getExpiringBatches(),
    ]);

    setOrders(orderData);

    setMedications(
      medicationData
    );

    setBatches(batchData);

    setMovements(
      movementData
    );

    setLowStock(
      lowStockData.length
    );

    setExpiringBatches(
      expiryData.length
    );

    if (
      !receiveMedicationId &&
      medicationData.length > 0
    ) {
      setReceiveMedicationId(
        medicationData[0].id
      );
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const medicationMap =
    useMemo(
      () =>
        new Map(
          medications.map(
            (medication) => [
              medication.id,
              medication,
            ]
          )
        ),
      [medications]
    );

  const totalUnits =
    medications.reduce(
      (total, medication) =>
        total +
        getMedicationStock(
          medication.id,
          batches
        ),
      0
    );

  const waitingOrders =
    orders.filter(
      (order) =>
        order.status !==
        "DISPENSED"
    ).length;

  const filteredOrders =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return orders;
      }

      return orders.filter(
        (order) =>
          order.patientName
            .toLowerCase()
            .includes(value) ||
          order.patientNumber
            .toLowerCase()
            .includes(value)
      );
    }, [
      orders,
      search,
    ]);

  const filteredMedications =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return medications;
      }

      return medications.filter(
        (medication) =>
          medication.name
            .toLowerCase()
            .includes(value) ||
          medication.genericName
            .toLowerCase()
            .includes(value)
      );
    }, [
      medications,
      search,
    ]);

  const filteredMovements =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return movements;
      }

      return movements.filter(
        (movement) => {
          const medication =
            medicationMap.get(
              movement.medicationId
            );

          return [
            medication?.name ?? "",
            movement.reference,
            movement.note ?? "",
          ]
            .join(" ")
            .toLowerCase()
            .includes(value);
        }
      );
    }, [
      movements,
      search,
      medicationMap,
    ]);

  async function handleReceive(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");

    try {
      await receiveStock(
        receiveMedicationId,
        receiveBatchNumber,
        receiveExpiry,
        Number(
          receiveQuantity
        )
      );

      setReceiveBatchNumber("");
      setReceiveExpiry("");
      setReceiveQuantity("");

      setShowReceiveModal(
        false
      );

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur de réception."
      );
    }
  }

  return (
    <div className="pharmacy-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 06 • PHARMACIE,
            STOCK & LOGISTIQUE
          </p>

          <h1>
            Pharmacie hospitalière
          </h1>

          <p className="subtitle">
            Ordonnances, délivrance,
            lots, expirations et
            mouvements de stock.
          </p>
        </div>

        <button
          className="primary-action"
          onClick={() =>
            setShowReceiveModal(
              true
            )
          }
        >
          <PackagePlus size={18} />
          Réception stock
        </button>
      </header>

      <section className="dashboard-stats">
        <article>
          <div className="stat-icon">
            <ClipboardList />
          </div>

          <div>
            <span>
              Ordonnances à traiter
            </span>

            <strong>
              {waitingOrders}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Boxes />
          </div>

          <div>
            <span>
              Unités en stock
            </span>

            <strong>
              {totalUnits}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <AlertTriangle />
          </div>

          <div>
            <span>
              Stocks faibles
            </span>

            <strong>
              {lowStock}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Truck />
          </div>

          <div>
            <span>
              Lots proches expiration
            </span>

            <strong>
              {expiringBatches}
            </strong>
          </div>
        </article>
      </section>

      <section className="pharmacy-tabs-card">
        <div className="pharmacy-toolbar">
          <div className="pharmacy-tabs">
            <button
              className={
                tab === "ORDERS"
                  ? "active"
                  : ""
              }
              onClick={() =>
                setTab("ORDERS")
              }
            >
              <ClipboardList
                size={16}
              />
              Ordonnances
            </button>

            <button
              className={
                tab === "STOCK"
                  ? "active"
                  : ""
              }
              onClick={() =>
                setTab("STOCK")
              }
            >
              <Boxes size={16} />
              Stock & lots
            </button>

            <button
              className={
                tab === "MOVEMENTS"
                  ? "active"
                  : ""
              }
              onClick={() =>
                setTab(
                  "MOVEMENTS"
                )
              }
            >
              <History size={16} />
              Mouvements
            </button>
          </div>

          <div className="patient-search pharmacy-search">
            <Search size={17} />

            <input
              value={search}
              onChange={(event) =>
                setSearch(
                  event.target.value
                )
              }
              placeholder="Rechercher..."
            />
          </div>
        </div>

        {tab === "ORDERS" && (
          <div className="patient-table-wrapper">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Numéro</th>
                  <th>Médicaments</th>
                  <th>Créée le</th>
                  <th>Statut</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {filteredOrders.map(
                  (order) => (
                    <tr
                      key={order.id}
                    >
                      <td>
                        <div className="patient-name">
                          <div className="patient-avatar">
                            {order.patientName
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <strong>
                            {
                              order.patientName
                            }
                          </strong>
                        </div>
                      </td>

                      <td>
                        <code>
                          {
                            order.patientNumber
                          }
                        </code>
                      </td>

                      <td>
                        {
                          order.items.length
                        }
                      </td>

                      <td>
                        {formatDate(
                          order.createdAt
                        )}
                      </td>

                      <td>
                        <span
                          className={`pharmacy-status ${order.status.toLowerCase()}`}
                        >
                          {orderStatusLabel(
                            order.status
                          )}
                        </span>
                      </td>

                      <td>
                        <button
                          className="table-action"
                          onClick={() =>
                            navigate(
                              `/pharmacie/ordonnances/${order.id}`
                            )
                          }
                        >
                          {order.status ===
                          "DISPENSED"
                            ? "Ouvrir"
                            : "Délivrer"}
                        </button>
                      </td>
                    </tr>
                  )
                )}

                {filteredOrders.length ===
                  0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="empty-table"
                    >
                      Aucune ordonnance.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {tab === "STOCK" && (
          <>
            <div className="pharmacy-section-title">
              <div>
                <span className="section-label">
                  CATALOGUE
                </span>

                <h2>
                  État du stock
                </h2>
              </div>
            </div>

            <div className="patient-table-wrapper">
              <table className="patient-table">
                <thead>
                  <tr>
                    <th>Médicament</th>
                    <th>Présentation</th>
                    <th>Prix</th>
                    <th>Stock</th>
                    <th>Seuil</th>
                    <th>État</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredMedications.map(
                    (medication) => {
                      const stock =
                        getMedicationStock(
                          medication.id,
                          batches
                        );

                      const isLow =
                        stock <=
                        medication.reorderLevel;

                      return (
                        <tr
                          key={
                            medication.id
                          }
                        >
                          <td>
                            <div className="patient-name">
                              <div className="patient-avatar">
                                <Pill
                                  size={16}
                                />
                              </div>

                              <div>
                                <strong>
                                  {
                                    medication.name
                                  }
                                </strong>

                                <span>
                                  {
                                    medication.genericName
                                  }
                                </span>
                              </div>
                            </div>
                          </td>

                          <td>
                            {
                              medication.form
                            }
                            {" • "}
                            {
                              medication.strength
                            }
                          </td>

                          <td>
                            {formatMoney(
                              medication.salePrice
                            )}
                          </td>

                          <td>
                            <strong>
                              {stock}
                            </strong>
                          </td>

                          <td>
                            {
                              medication.reorderLevel
                            }
                          </td>

                          <td>
                            <span
                              className={
                                isLow
                                  ? "stock-state low"
                                  : "stock-state good"
                              }
                            >
                              {isLow
                                ? "Stock faible"
                                : "Disponible"}
                            </span>
                          </td>
                        </tr>
                      );
                    }
                  )}
                </tbody>
              </table>
            </div>

            <div className="pharmacy-section-title pharmacy-lots-title">
              <div>
                <span className="section-label">
                  TRAÇABILITÉ
                </span>

                <h2>
                  Lots en stock
                </h2>
              </div>
            </div>

            <div className="patient-table-wrapper">
              <table className="patient-table">
                <thead>
                  <tr>
                    <th>Lot</th>
                    <th>Médicament</th>
                    <th>Expiration</th>
                    <th>Quantité</th>
                    <th>Réception</th>
                  </tr>
                </thead>

                <tbody>
                  {batches.map(
                    (batch) => (
                      <tr
                        key={
                          batch.id
                        }
                      >
                        <td>
                          <code>
                            {
                              batch.batchNumber
                            }
                          </code>
                        </td>

                        <td>
                          {medicationMap.get(
                            batch.medicationId
                          )?.name ??
                            "Médicament inconnu"}
                        </td>

                        <td>
                          {
                            batch.expiryDate
                          }
                        </td>

                        <td>
                          <strong>
                            {
                              batch.quantity
                            }
                          </strong>
                        </td>

                        <td>
                          {formatDate(
                            batch.receivedAt
                          )}
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === "MOVEMENTS" && (
          <div className="patient-table-wrapper">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Médicament</th>
                  <th>Quantité</th>
                  <th>Référence</th>
                  <th>Note</th>
                </tr>
              </thead>

              <tbody>
                {filteredMovements.map(
                  (movement) => (
                    <tr
                      key={
                        movement.id
                      }
                    >
                      <td>
                        {formatDate(
                          movement.createdAt
                        )}
                      </td>

                      <td>
                        <span
                          className={`movement-type ${movement.type.toLowerCase()}`}
                        >
                          {movementLabel(
                            movement.type
                          )}
                        </span>
                      </td>

                      <td>
                        {medicationMap.get(
                          movement.medicationId
                        )?.name ??
                          "Inconnu"}
                      </td>

                      <td>
                        <strong>
                          {movement.type ===
                          "DISPENSE"
                            ? "-"
                            : "+"}
                          {
                            movement.quantity
                          }
                        </strong>
                      </td>

                      <td>
                        <code>
                          {
                            movement.reference
                          }
                        </code>
                      </td>

                      <td>
                        {movement.note ||
                          "—"}
                      </td>
                    </tr>
                  )
                )}

                {filteredMovements.length ===
                  0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="empty-table"
                    >
                      Aucun mouvement
                      enregistré.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showReceiveModal && (
        <div className="modal-backdrop">
          <form
            className="patient-modal compact-modal"
            onSubmit={
              handleReceive
            }
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  LOGISTIQUE
                </span>

                <h2>
                  Réception de stock
                </h2>

                <p>
                  Ajouter un nouveau
                  lot de médicament.
                </p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setShowReceiveModal(
                    false
                  )
                }
              >
                <X size={20} />
              </button>
            </div>

            {error && (
              <div className="login-error">
                {error}
              </div>
            )}

            <label className="modal-label">
              Médicament

              <select
                value={
                  receiveMedicationId
                }
                onChange={(event) =>
                  setReceiveMedicationId(
                    event.target.value
                  )
                }
              >
                {medications.map(
                  (medication) => (
                    <option
                      key={
                        medication.id
                      }
                      value={
                        medication.id
                      }
                    >
                      {medication.name}
                      {" • "}
                      {
                        medication.strength
                      }
                    </option>
                  )
                )}
              </select>
            </label>

            <label className="modal-label">
              Numéro de lot

              <input
                value={
                  receiveBatchNumber
                }
                onChange={(event) =>
                  setReceiveBatchNumber(
                    event.target.value
                  )
                }
                placeholder="LOT-2026-001"
                required
              />
            </label>

            <label className="modal-label">
              Date d'expiration

              <input
                type="date"
                value={
                  receiveExpiry
                }
                onChange={(event) =>
                  setReceiveExpiry(
                    event.target.value
                  )
                }
                required
              />
            </label>

            <label className="modal-label">
              Quantité reçue

              <input
                type="number"
                min="1"
                step="1"
                value={
                  receiveQuantity
                }
                onChange={(event) =>
                  setReceiveQuantity(
                    event.target.value
                  )
                }
                required
              />
            </label>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setShowReceiveModal(
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
                <PackagePlus
                  size={17}
                />
                Enregistrer réception
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
