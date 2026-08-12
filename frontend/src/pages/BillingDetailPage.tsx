import {
  ArrowLeft,
  Banknote,
  CheckCircle2,
  Download,
  Printer,
  ReceiptText,
} from "lucide-react";

import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import {
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  getInvoice,
  invoiceBalance,
  invoicePaid,
  invoiceTotal,
  registerPayment,
} from "../services/billingService";

import {
  exportInvoicePdf,
  exportPaymentReceiptPdf,
  printInvoice,
  printPaymentReceipt,
} from "../services/documentService";

import type {
  Invoice,
  InvoicePayment,
  PaymentMethod,
} from "../types/billing";

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
  ).format(
    new Date(value)
  );
}

function paymentMethodLabel(
  method: PaymentMethod
) {
  switch (method) {
    case "CASH":
      return "Espèces";

    case "MOBILE_MONEY":
      return "Mobile Money";

    case "BANK":
      return "Banque";

    case "CARD":
      return "Carte";
  }
}

function statusLabel(
  status: Invoice["status"]
) {
  if (status === "OPEN") {
    return "À payer";
  }

  if (status === "PARTIAL") {
    return "Paiement partiel";
  }

  return "Payée";
}

export default function BillingDetailPage() {
  const navigate =
    useNavigate();

  const { invoiceId } =
    useParams();

  const [invoice, setInvoice] =
    useState<Invoice | null>(
      null
    );

  const [amount, setAmount] =
    useState("");

  const [method, setMethod] =
    useState<PaymentMethod>(
      "CASH"
    );

  const [reference, setReference] =
    useState("");

  const [error, setError] =
    useState("");

  const [
    lastPayment,
    setLastPayment,
  ] =
    useState<InvoicePayment | null>(
      null
    );

  const [loading, setLoading] =
    useState(true);

  async function load() {
    if (!invoiceId) {
      return;
    }

    setInvoice(
      await getInvoice(
        invoiceId
      )
    );

    setLoading(false);
  }

  useEffect(() => {
    load();
  }, [invoiceId]);

  async function handlePayment(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!invoice) {
      return;
    }

    setError("");

    const numericAmount =
      Number(amount);

    try {
      const updated =
        await registerPayment(
          invoice.id,
          numericAmount,
          method,
          reference
        );

      setInvoice(updated);

      const payment =
        updated.payments[
          updated.payments.length - 1
        ];

      setLastPayment(
        payment ?? null
      );

      setAmount("");
      setReference("");
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Erreur pendant le paiement."
      );
    }
  }

  if (loading) {
    return (
      <div className="patient-detail-state">
        Chargement de la facture...
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="patient-detail-state">
        <h2>
          Facture introuvable
        </h2>

        <button
          className="primary-action"
          onClick={() =>
            navigate("/paiement")
          }
        >
          Retour
        </button>
      </div>
    );
  }

  const total =
    invoiceTotal(invoice);

  const paid =
    invoicePaid(invoice);

  const balance =
    invoiceBalance(invoice);

  return (
    <div className="billing-detail-page">
      <button
        className="back-link"
        onClick={() =>
          navigate("/paiement")
        }
      >
        <ArrowLeft size={17} />
        Retour aux factures
      </button>

      <section className="billing-document-header">
        <div>
          <p className="eyebrow">
            FACTURE PATIENT
          </p>

          <h1>
            {invoice.invoiceNumber}
          </h1>

          <div className="profile-meta">
            <span>
              {invoice.patientName}
            </span>

            <span>
              {invoice.patientNumber}
            </span>

            <span>
              {formatDate(
                invoice.createdAt
              )}
            </span>
          </div>
        </div>

        <div className="billing-header-actions">
          <span
            className={`billing-status ${invoice.status.toLowerCase()}`}
          >
            {statusLabel(
              invoice.status
            )}
          </span>

          <button
            className="secondary-action billing-action-button"
            onClick={() =>
              exportInvoicePdf(
                invoice
              )
            }
          >
            <Download size={16} />
            PDF
          </button>

          <button
            className="secondary-action billing-action-button"
            onClick={() =>
              printInvoice(
                invoice
              )
            }
          >
            <Printer size={16} />
            Imprimer
          </button>
        </div>
      </section>

      <section className="billing-summary">
        <article>
          <span>
            Total facture
          </span>

          <strong>
            {formatMoney(total)}
          </strong>
        </article>

        <article>
          <span>
            Montant payé
          </span>

          <strong>
            {formatMoney(paid)}
          </strong>
        </article>

        <article
          className={
            balance === 0
              ? "billing-paid-summary"
              : ""
          }
        >
          <span>
            Reste à payer
          </span>

          <strong>
            {formatMoney(balance)}
          </strong>
        </article>
      </section>

      <section className="billing-workspace">
        <article className="billing-invoice-card">
          <div className="section-header">
            <div>
              <span className="section-label">
                DÉTAIL DE FACTURATION
              </span>

              <h2>
                Prestations facturées
              </h2>
            </div>

            <ReceiptText />
          </div>

          <div className="patient-table-wrapper">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Prestation</th>
                  <th>Source</th>
                  <th>Qté</th>
                  <th>Prix unitaire</th>
                  <th>Total</th>
                </tr>
              </thead>

              <tbody>
                {invoice.items.map(
                  (item) => (
                    <tr
                      key={item.id}
                    >
                      <td>
                        <strong>
                          {item.description}
                        </strong>
                      </td>

                      <td>
                        {item.sourceType}
                      </td>

                      <td>
                        {item.quantity}
                      </td>

                      <td>
                        {formatMoney(
                          item.unitPrice
                        )}
                      </td>

                      <td>
                        <strong>
                          {formatMoney(
                            item.total
                          )}
                        </strong>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="payment-panel">
          <div className="payment-panel-icon">
            <Banknote />
          </div>

          <span className="section-label">
            ENCAISSEMENT
          </span>

          <h2>
            Enregistrer un paiement
          </h2>

          {balance > 0 ? (
            <form
              onSubmit={
                handlePayment
              }
            >
              {error && (
                <div className="login-error">
                  {error}
                </div>
              )}

              <label className="payment-label">
                Montant BIF

                <input
                  type="number"
                  min="1"
                  max={balance}
                  value={amount}
                  onChange={(event) =>
                    setAmount(
                      event.target.value
                    )
                  }
                  placeholder={String(
                    balance
                  )}
                  required
                />
              </label>

              <button
                type="button"
                className="pay-full-balance"
                onClick={() =>
                  setAmount(
                    String(balance)
                  )
                }
              >
                Utiliser le solde complet
                {" • "}
                {formatMoney(balance)}
              </button>

              <label className="payment-label">
                Mode de paiement

                <select
                  value={method}
                  onChange={(event) =>
                    setMethod(
                      event.target
                        .value as PaymentMethod
                    )
                  }
                >
                  <option value="CASH">
                    Espèces
                  </option>

                  <option value="MOBILE_MONEY">
                    Mobile Money
                  </option>

                  <option value="BANK">
                    Banque
                  </option>

                  <option value="CARD">
                    Carte
                  </option>
                </select>
              </label>

              <label className="payment-label">
                Référence

                <input
                  value={reference}
                  onChange={(event) =>
                    setReference(
                      event.target.value
                    )
                  }
                  placeholder="Optionnel"
                />
              </label>

              <button
                className="primary-action payment-submit"
                type="submit"
              >
                <Banknote size={17} />
                Enregistrer paiement
              </button>
            </form>
          ) : (
            <div className="invoice-paid-box">
              <CheckCircle2 />
              <strong>
                Facture entièrement payée
              </strong>

              <span>
                Aucun solde restant.
              </span>
            </div>
          )}
        </aside>
      </section>

      {lastPayment && (
        <section className="payment-success-card">
          <div>
            <CheckCircle2 />
          </div>

          <div>
            <span className="section-label">
              PAIEMENT ENREGISTRÉ
            </span>

            <h2>
              {formatMoney(
                lastPayment.amount
              )}
            </h2>

            <p>
              {paymentMethodLabel(
                lastPayment.method
              )}
              {" • "}
              {formatDate(
                lastPayment.paidAt
              )}
            </p>
          </div>

          <div className="payment-success-actions">
            <button
              className="secondary-action billing-action-button"
              onClick={() =>
                exportPaymentReceiptPdf(
                  invoice,
                  lastPayment
                )
              }
            >
              <Download size={16} />
              Reçu PDF
            </button>

            <button
              className="secondary-action billing-action-button"
              onClick={() =>
                printPaymentReceipt(
                  invoice,
                  lastPayment
                )
              }
            >
              <Printer size={16} />
              Imprimer reçu
            </button>
          </div>
        </section>
      )}

      <section className="billing-history-card">
        <div className="section-header">
          <div>
            <span className="section-label">
              TRAÇABILITÉ FINANCIÈRE
            </span>

            <h2>
              Historique des paiements
            </h2>
          </div>

          <span className="module-count">
            {invoice.payments.length}
            {" "}
            paiement(s)
          </span>
        </div>

        {invoice.payments.length > 0 ? (
          <div className="patient-table-wrapper">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Mode</th>
                  <th>Référence</th>
                  <th>Montant</th>
                  <th>Reçu</th>
                </tr>
              </thead>

              <tbody>
                {invoice.payments.map(
                  (payment) => (
                    <tr
                      key={payment.id}
                    >
                      <td>
                        {formatDate(
                          payment.paidAt
                        )}
                      </td>

                      <td>
                        {paymentMethodLabel(
                          payment.method
                        )}
                      </td>

                      <td>
                        {payment.reference ||
                          "—"}
                      </td>

                      <td>
                        <strong>
                          {formatMoney(
                            payment.amount
                          )}
                        </strong>
                      </td>

                      <td>
                        <div className="table-actions">
                          <button
                            className="table-action"
                            onClick={() =>
                              exportPaymentReceiptPdf(
                                invoice,
                                payment
                              )
                            }
                          >
                            PDF
                          </button>

                          <button
                            className="table-action"
                            onClick={() =>
                              printPaymentReceipt(
                                invoice,
                                payment
                              )
                            }
                          >
                            Imprimer
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-history">
            Aucun paiement enregistré.
          </div>
        )}
      </section>
    </div>
  );
}
