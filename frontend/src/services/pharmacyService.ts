import {
  listConsultations,
} from "./consultationService";

import {
  addServiceCharge,
} from "./billingService";

import type {
  Medication,
  PharmacyOrder,
  PharmacyOrderItem,
  StockBatch,
  StockMovement,
} from "../types/pharmacy";

const MEDICATIONS_KEY =
  "hospitalis_medications";

const BATCHES_KEY =
  "hospitalis_stock_batches";

const MOVEMENTS_KEY =
  "hospitalis_stock_movements";

const ORDERS_KEY =
  "hospitalis_pharmacy_orders";

const defaultMedications:
  Medication[] = [
  {
    id: "MED-PARACETAMOL",
    name: "Paracétamol",
    genericName:
      "Paracétamol",
    form: "Comprimé",
    strength: "500 mg",
    unit: "comprimé",
    salePrice: 500,
    reorderLevel: 20,
    active: true,
  },

  {
    id: "MED-AMOXICILLINE",
    name: "Amoxicilline",
    genericName:
      "Amoxicilline",
    form: "Gélule",
    strength: "500 mg",
    unit: "gélule",
    salePrice: 1200,
    reorderLevel: 20,
    active: true,
  },

  {
    id: "MED-IBUPROFENE",
    name: "Ibuprofène",
    genericName:
      "Ibuprofène",
    form: "Comprimé",
    strength: "400 mg",
    unit: "comprimé",
    salePrice: 800,
    reorderLevel: 15,
    active: true,
  },

  {
    id: "MED-CEFTRIAXONE",
    name: "Ceftriaxone",
    genericName:
      "Ceftriaxone",
    form: "Injectable",
    strength: "1 g",
    unit: "flacon",
    salePrice: 3500,
    reorderLevel: 10,
    active: true,
  },

  {
    id: "MED-FER-FOLIQUE",
    name: "Fer + acide folique",
    genericName:
      "Fer / Acide folique",
    form: "Comprimé",
    strength: "Standard",
    unit: "comprimé",
    salePrice: 700,
    reorderLevel: 30,
    active: true,
  },

  {
    id: "MED-OXYTOCINE",
    name: "Oxytocine",
    genericName:
      "Oxytocine",
    form: "Injectable",
    strength: "10 UI",
    unit: "ampoule",
    salePrice: 1800,
    reorderLevel: 10,
    active: true,
  },
];

const defaultBatches:
  StockBatch[] = [
  {
    id: "LOT-PARA-001",
    medicationId:
      "MED-PARACETAMOL",
    batchNumber:
      "PARA-26001",
    expiryDate:
      "2027-06-30",
    quantity: 150,
    receivedAt:
      new Date().toISOString(),
  },

  {
    id: "LOT-PARA-002",
    medicationId:
      "MED-PARACETAMOL",
    batchNumber:
      "PARA-26002",
    expiryDate:
      "2028-01-31",
    quantity: 200,
    receivedAt:
      new Date().toISOString(),
  },

  {
    id: "LOT-AMOX-001",
    medicationId:
      "MED-AMOXICILLINE",
    batchNumber:
      "AMOX-26001",
    expiryDate:
      "2027-04-30",
    quantity: 90,
    receivedAt:
      new Date().toISOString(),
  },

  {
    id: "LOT-IBU-001",
    medicationId:
      "MED-IBUPROFENE",
    batchNumber:
      "IBU-26001",
    expiryDate:
      "2027-08-31",
    quantity: 75,
    receivedAt:
      new Date().toISOString(),
  },

  {
    id: "LOT-CEF-001",
    medicationId:
      "MED-CEFTRIAXONE",
    batchNumber:
      "CEF-26001",
    expiryDate:
      "2027-03-31",
    quantity: 30,
    receivedAt:
      new Date().toISOString(),
  },

  {
    id: "LOT-FER-001",
    medicationId:
      "MED-FER-FOLIQUE",
    batchNumber:
      "FER-26001",
    expiryDate:
      "2028-02-28",
    quantity: 120,
    receivedAt:
      new Date().toISOString(),
  },

  {
    id: "LOT-OXY-001",
    medicationId:
      "MED-OXYTOCINE",
    batchNumber:
      "OXY-26001",
    expiryDate:
      "2027-05-31",
    quantity: 25,
    receivedAt:
      new Date().toISOString(),
  },
];

function loadMedications():
  Medication[] {
  const stored =
    localStorage.getItem(
      MEDICATIONS_KEY
    );

  if (!stored) {
    localStorage.setItem(
      MEDICATIONS_KEY,
      JSON.stringify(
        defaultMedications
      )
    );

    return defaultMedications;
  }

  try {
    return JSON.parse(
      stored
    ) as Medication[];
  } catch {
    return [];
  }
}

function loadBatches():
  StockBatch[] {
  const stored =
    localStorage.getItem(
      BATCHES_KEY
    );

  if (!stored) {
    localStorage.setItem(
      BATCHES_KEY,
      JSON.stringify(
        defaultBatches
      )
    );

    return defaultBatches;
  }

  try {
    return JSON.parse(
      stored
    ) as StockBatch[];
  } catch {
    return [];
  }
}

function saveBatches(
  batches: StockBatch[]
) {
  localStorage.setItem(
    BATCHES_KEY,
    JSON.stringify(batches)
  );
}

function loadMovements():
  StockMovement[] {
  const stored =
    localStorage.getItem(
      MOVEMENTS_KEY
    );

  if (!stored) {
    return [];
  }

  try {
    return JSON.parse(
      stored
    ) as StockMovement[];
  } catch {
    return [];
  }
}

function saveMovements(
  movements: StockMovement[]
) {
  localStorage.setItem(
    MOVEMENTS_KEY,
    JSON.stringify(movements)
  );
}

function loadOrders():
  PharmacyOrder[] {
  const stored =
    localStorage.getItem(
      ORDERS_KEY
    );

  if (!stored) {
    return [];
  }

  try {
    return JSON.parse(
      stored
    ) as PharmacyOrder[];
  } catch {
    return [];
  }
}

function saveOrders(
  orders: PharmacyOrder[]
) {
  localStorage.setItem(
    ORDERS_KEY,
    JSON.stringify(orders)
  );
}

function normalize(
  value: string
) {
  return value
    .normalize("NFD")
    .replace(
      /[\u0300-\u036f]/g,
      ""
    )
    .trim()
    .toLowerCase();
}

function findMedicationForPrescription(
  prescribedName: string,
  medications: Medication[]
) {
  const prescribed =
    normalize(
      prescribedName
    );

  return medications.find(
    (medication) => {
      const name =
        normalize(
          medication.name
        );

      const generic =
        normalize(
          medication.genericName
        );

      return (
        prescribed.includes(
          name
        ) ||
        name.includes(
          prescribed
        ) ||
        prescribed.includes(
          generic
        ) ||
        generic.includes(
          prescribed
        )
      );
    }
  );
}

export async function listMedications():
  Promise<Medication[]> {
  return loadMedications();
}

export async function listStockBatches():
  Promise<StockBatch[]> {
  return loadBatches();
}

export async function listStockMovements():
  Promise<StockMovement[]> {
  return loadMovements();
}

export function getMedicationStock(
  medicationId: string,
  batches = loadBatches()
) {
  const today =
    new Date()
      .toISOString()
      .slice(0, 10);

  return batches
    .filter(
      (batch) =>
        batch.medicationId ===
          medicationId &&
        batch.expiryDate >=
          today
    )
    .reduce(
      (total, batch) =>
        total +
        batch.quantity,
      0
    );
}

export async function synchronizePharmacyOrders():
  Promise<PharmacyOrder[]> {
  const consultations =
    await listConsultations();

  const medications =
    loadMedications();

  const orders =
    loadOrders();

  let changed = false;

  for (
    const consultation
    of consultations
  ) {
    if (
      consultation
        .prescriptions.length === 0
    ) {
      continue;
    }

    const exists =
      orders.some(
        (order) =>
          order.consultationId ===
          consultation.id
      );

    if (exists) {
      continue;
    }

    const items:
      PharmacyOrderItem[] =
      consultation.prescriptions.map(
        (prescription) => {
          const medication =
            findMedicationForPrescription(
              prescription.medicine,
              medications
            );

          return {
            id:
              crypto.randomUUID(),

            prescriptionItemId:
              prescription.id,

            prescribedName:
              prescription.medicine,

            dosage:
              prescription.dosage,

            frequency:
              prescription.frequency,

            duration:
              prescription.duration,

            medicationId:
              medication?.id,

            requestedQuantity: 1,

            dispensedQuantity: 0,
          };
        }
      );

    orders.unshift({
      id:
        crypto.randomUUID(),

      consultationId:
        consultation.id,

      patientId:
        consultation.patientId,

      patientNumber:
        consultation.patientNumber,

      patientName:
        consultation.patientName,

      status:
        "WAITING",

      items,

      createdAt:
        new Date().toISOString(),
    });

    changed = true;
  }

  if (changed) {
    saveOrders(
      orders
    );
  }

  return orders;
}

export async function listPharmacyOrders():
  Promise<PharmacyOrder[]> {
  await synchronizePharmacyOrders();

  return loadOrders();
}

export async function getPharmacyOrder(
  orderId: string
): Promise<PharmacyOrder | null> {
  await synchronizePharmacyOrders();

  return (
    loadOrders().find(
      (order) =>
        order.id === orderId
    ) ?? null
  );
}

export async function assignMedication(
  orderId: string,
  itemId: string,
  medicationId: string
): Promise<PharmacyOrder> {
  const orders =
    loadOrders();

  const orderIndex =
    orders.findIndex(
      (order) =>
        order.id === orderId
    );

  if (orderIndex === -1) {
    throw new Error(
      "Ordonnance introuvable"
    );
  }

  const itemIndex =
    orders[
      orderIndex
    ].items.findIndex(
      (item) =>
        item.id === itemId
    );

  if (itemIndex === -1) {
    throw new Error(
      "Ligne de prescription introuvable"
    );
  }

  orders[
    orderIndex
  ].items[
    itemIndex
  ] = {
    ...orders[
      orderIndex
    ].items[
      itemIndex
    ],

    medicationId,
  };

  saveOrders(
    orders
  );

  return orders[
    orderIndex
  ];
}

export async function setRequestedQuantity(
  orderId: string,
  itemId: string,
  quantity: number
): Promise<PharmacyOrder> {
  if (
    !Number.isInteger(
      quantity
    ) ||
    quantity <= 0
  ) {
    throw new Error(
      "Quantité invalide"
    );
  }

  const orders =
    loadOrders();

  const orderIndex =
    orders.findIndex(
      (order) =>
        order.id === orderId
    );

  if (orderIndex === -1) {
    throw new Error(
      "Ordonnance introuvable"
    );
  }

  const itemIndex =
    orders[
      orderIndex
    ].items.findIndex(
      (item) =>
        item.id === itemId
    );

  if (itemIndex === -1) {
    throw new Error(
      "Ligne introuvable"
    );
  }

  const current =
    orders[
      orderIndex
    ].items[
      itemIndex
    ];

  if (
    quantity <
    current.dispensedQuantity
  ) {
    throw new Error(
      "La quantité demandée ne peut pas être inférieure à la quantité déjà délivrée"
    );
  }

  orders[
    orderIndex
  ].items[
    itemIndex
  ] = {
    ...current,
    requestedQuantity:
      quantity,
  };

  saveOrders(
    orders
  );

  return orders[
    orderIndex
  ];
}

export async function receiveStock(
  medicationId: string,
  batchNumber: string,
  expiryDate: string,
  quantity: number
): Promise<StockBatch> {
  if (
    !Number.isInteger(
      quantity
    ) ||
    quantity <= 0
  ) {
    throw new Error(
      "Quantité reçue invalide"
    );
  }

  if (
    !batchNumber.trim()
  ) {
    throw new Error(
      "Numéro de lot obligatoire"
    );
  }

  const medications =
    loadMedications();

  const medication =
    medications.find(
      (item) =>
        item.id ===
        medicationId
    );

  if (!medication) {
    throw new Error(
      "Médicament introuvable"
    );
  }

  const batches =
    loadBatches();

  const movements =
    loadMovements();

  const batch:
    StockBatch = {
    id:
      crypto.randomUUID(),

    medicationId,

    batchNumber:
      batchNumber.trim(),

    expiryDate,

    quantity,

    receivedAt:
      new Date().toISOString(),
  };

  batches.push(
    batch
  );

  movements.unshift({
    id:
      crypto.randomUUID(),

    medicationId,

    batchId:
      batch.id,

    type:
      "RECEIVE",

    quantity,

    reference:
      `RECEPTION-${batch.batchNumber}`,

    note:
      `Réception ${medication.name}`,

    createdAt:
      new Date().toISOString(),
  });

  saveBatches(
    batches
  );

  saveMovements(
    movements
  );

  return batch;
}

export async function dispenseOrderItem(
  orderId: string,
  itemId: string,
  quantity: number
): Promise<PharmacyOrder> {
  if (
    !Number.isInteger(
      quantity
    ) ||
    quantity <= 0
  ) {
    throw new Error(
      "Quantité à délivrer invalide"
    );
  }

  const orders =
    loadOrders();

  const medications =
    loadMedications();

  const batches =
    loadBatches();

  const movements =
    loadMovements();

  const orderIndex =
    orders.findIndex(
      (order) =>
        order.id === orderId
    );

  if (orderIndex === -1) {
    throw new Error(
      "Ordonnance introuvable"
    );
  }

  const order =
    orders[
      orderIndex
    ];

  const itemIndex =
    order.items.findIndex(
      (item) =>
        item.id === itemId
    );

  if (itemIndex === -1) {
    throw new Error(
      "Médicament prescrit introuvable"
    );
  }

  const item =
    order.items[
      itemIndex
    ];

  if (!item.medicationId) {
    throw new Error(
      "Associez d'abord la prescription à un médicament du stock"
    );
  }

  const medication =
    medications.find(
      (current) =>
        current.id ===
        item.medicationId
    );

  if (!medication) {
    throw new Error(
      "Médicament du stock introuvable"
    );
  }

  const remaining =
    item.requestedQuantity -
    item.dispensedQuantity;

  if (
    quantity >
    remaining
  ) {
    throw new Error(
      "La quantité dépasse le reste à délivrer"
    );
  }

  const today =
    new Date()
      .toISOString()
      .slice(0, 10);

  const availableBatches =
    batches
      .filter(
        (batch) =>
          batch.medicationId ===
            medication.id &&
          batch.quantity > 0 &&
          batch.expiryDate >=
            today
      )
      .sort(
        (a, b) =>
          a.expiryDate.localeCompare(
            b.expiryDate
          )
      );

  const totalAvailable =
    availableBatches.reduce(
      (total, batch) =>
        total +
        batch.quantity,
      0
    );

  if (
    totalAvailable <
    quantity
  ) {
    throw new Error(
      `Stock insuffisant. Disponible : ${totalAvailable}`
    );
  }

  let quantityToRemove =
    quantity;

  const dispenseReference =
    `DEL-${crypto.randomUUID()}`;

  for (
    const batch
    of availableBatches
  ) {
    if (
      quantityToRemove <= 0
    ) {
      break;
    }

    const deduction =
      Math.min(
        batch.quantity,
        quantityToRemove
      );

    const realBatch =
      batches.find(
        (current) =>
          current.id ===
          batch.id
      );

    if (!realBatch) {
      continue;
    }

    realBatch.quantity -=
      deduction;

    quantityToRemove -=
      deduction;

    movements.unshift({
      id:
        crypto.randomUUID(),

      medicationId:
        medication.id,

      batchId:
        batch.id,

      type:
        "DISPENSE",

      quantity:
        deduction,

      reference:
        dispenseReference,

      note:
        `${order.patientName} - ${medication.name}`,

      createdAt:
        new Date().toISOString(),
    });
  }

  order.items[
    itemIndex
  ] = {
    ...item,

    dispensedQuantity:
      item.dispensedQuantity +
      quantity,
  };

  const allCompleted =
    order.items.every(
      (current) =>
        current.dispensedQuantity >=
        current.requestedQuantity
    );

  const anyDispensed =
    order.items.some(
      (current) =>
        current.dispensedQuantity >
        0
    );

  order.status =
    allCompleted
      ? "DISPENSED"
      : anyDispensed
        ? "PARTIAL"
        : "WAITING";

  if (allCompleted) {
    order.dispensedAt =
      new Date().toISOString();
  }

  orders[
    orderIndex
  ] = order;

  saveBatches(
    batches
  );

  saveMovements(
    movements
  );

  saveOrders(
    orders
  );

  await addServiceCharge({
    patientId:
      order.patientId,

    patientNumber:
      order.patientNumber,

    patientName:
      order.patientName,

    sourceType:
      "PHARMACY",

    sourceId:
      dispenseReference,

    description:
      `${medication.name} ${medication.strength} x ${quantity}`,

    amount:
      medication.salePrice *
      quantity,
  });

  return order;
}

export async function getLowStockMedications():
  Promise<
    Array<{
      medication: Medication;
      stock: number;
    }>
  > {
  const medications =
    loadMedications();

  const batches =
    loadBatches();

  return medications
    .map(
      (medication) => ({
        medication,

        stock:
          getMedicationStock(
            medication.id,
            batches
          ),
      })
    )
    .filter(
      ({ medication, stock }) =>
        stock <=
        medication.reorderLevel
    );
}

export async function getExpiringBatches(
  days = 90
): Promise<StockBatch[]> {
  const now =
    new Date();

  const limit =
    new Date();

  limit.setDate(
    limit.getDate() +
      days
  );

  return loadBatches()
    .filter(
      (batch) => {
        if (
          batch.quantity <= 0
        ) {
          return false;
        }

        const expiry =
          new Date(
            `${batch.expiryDate}T00:00:00`
          );

        return (
          expiry >= now &&
          expiry <= limit
        );
      }
    )
    .sort(
      (a, b) =>
        a.expiryDate.localeCompare(
          b.expiryDate
        )
    );
}
