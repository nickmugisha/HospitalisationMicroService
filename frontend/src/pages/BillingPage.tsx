import {
  Banknote,
  CircleDollarSign,
  CreditCard,
  ReceiptText,
  Search,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  invoiceBalance,
  invoicePaid,
  invoiceTotal,
  listInvoices,
} from "../services/billingService";

import type {
  Invoice,
} from "../types/billing";

function formatMoney(
  amount: number
) {
  return `${new Intl.NumberFormat(
    "fr-FR"
  ).format(amount)} BIF`;
}

function statusLabel(
  status: Invoice["status"]
) {
  if (status === "OPEN") {
    return "À payer";
  }

  if (status === "PARTIAL") {
    return "Partiel";
  }

  return "Payée";
}

export default function BillingPage() {
  const navigate =
    useNavigate();

  const [invoices, setInvoices] =
    useState<Invoice[]>([]);

  const [search, setSearch] =
    useState("");

  async function refresh() {
    setInvoices(
      await listInvoices()
    );
  }

  useEffect(() => {
    refresh();
  }, []);

  const filtered =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return invoices;
      }

      return invoices.filter(
        (invoice) =>
          invoice.patientName
            .toLowerCase()
            .includes(value) ||
          invoice.patientNumber
            .toLowerCase()
            .includes(value) ||
          invoice.invoiceNumber
            .toLowerCase()
            .includes(value)
      );
    }, [
      invoices,
      search,
    ]);

  const totalBilled =
    invoices.reduce(
      (total, invoice) =>
        total +
        invoiceTotal(invoice),
      0
    );

  const totalPaid =
    invoices.reduce(
      (total, invoice) =>
        total +
        invoicePaid(invoice),
      0
    );

  const totalBalance =
    invoices.reduce(
      (total, invoice) =>
        total +
        invoiceBalance(invoice),
      0
    );

  const unpaidInvoices =
    invoices.filter(
      (invoice) =>
        invoice.status !== "PAID"
    ).length;

  return (
    <div className="billing-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 03 • PAIEMENT & FACTURATION
          </p>

          <h1>
            Paiement & facturation
          </h1>

          <p className="subtitle">
            Factures patients, prestations,
            paiements, soldes et reçus.
          </p>
        </div>

        <div className="consultation-live">
          <span className="client-dot" />
          Facturation synchronisée
        </div>
      </header>

      <section className="dashboard-stats">
        <article>
          <div className="stat-icon">
            <ReceiptText />
          </div>

          <div>
            <span>
              Total facturé
            </span>

            <strong>
              {formatMoney(
                totalBilled
              )}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Banknote />
          </div>

          <div>
            <span>
              Total encaissé
            </span>

            <strong>
              {formatMoney(
                totalPaid
              )}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <CircleDollarSign />
          </div>

          <div>
            <span>
              Reste à payer
            </span>

            <strong>
              {formatMoney(
                totalBalance
              )}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <CreditCard />
          </div>

          <div>
            <span>
              Factures ouvertes
            </span>

            <strong>
              {unpaidInvoices}
            </strong>
          </div>
        </article>
      </section>

      <section className="consultation-list-card">
        <div className="panel-heading">
          <div>
            <span className="section-label">
              FACTURES PATIENTS
            </span>

            <h2>
              Registre de facturation
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
              placeholder="Patient, numéro, facture..."
            />
          </div>
        </div>

        <div className="patient-table-wrapper">
          <table className="patient-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Facture</th>
                <th>Prestations</th>
                <th>Total</th>
                <th>Payé</th>
                <th>Reste</th>
                <th>Statut</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map(
                (invoice) => (
                  <tr key={invoice.id}>
                    <td>
                      <div className="patient-name">
                        <div className="patient-avatar">
                          {invoice.patientName
                            .charAt(0)
                            .toUpperCase()}
                        </div>

                        <div>
                          <strong>
                            {invoice.patientName}
                          </strong>

                          <span>
                            {invoice.patientNumber}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <code>
                        {invoice.invoiceNumber}
                      </code>
                    </td>

                    <td>
                      {invoice.items.length}
                    </td>

                    <td>
                      <strong>
                        {formatMoney(
                          invoiceTotal(
                            invoice
                          )
                        )}
                      </strong>
                    </td>

                    <td>
                      {formatMoney(
                        invoicePaid(
                          invoice
                        )
                      )}
                    </td>

                    <td>
                      <strong>
                        {formatMoney(
                          invoiceBalance(
                            invoice
                          )
                        )}
                      </strong>
                    </td>

                    <td>
                      <span
                        className={`billing-status ${invoice.status.toLowerCase()}`}
                      >
                        {statusLabel(
                          invoice.status
                        )}
                      </span>
                    </td>

                    <td>
                      <button
                        className="table-action"
                        onClick={() =>
                          navigate(
                            `/paiement/${invoice.id}`
                          )
                        }
                      >
                        Ouvrir
                      </button>
                    </td>
                  </tr>
                )
              )}

              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="empty-table"
                  >
                    Aucune facture disponible.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
