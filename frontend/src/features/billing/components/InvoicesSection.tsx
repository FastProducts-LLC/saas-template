import { formatMoney } from "../../../shared/lib/money";
import { SectionRule, Spinner, Stamp, ErrorAlert } from "../../../shared/ui";
import { useInvoices } from "../api/hooks";
import type { Invoice } from "../model/types";

interface InvoicesSectionProps {
  orgId: string;
  /** Only fetch/render for admins/owners — members get a 403 from the API. */
  enabled: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  paid: "border-[var(--success)] text-[var(--success)]",
  open: "border-[var(--info)] text-[var(--info)]",
  draft: "border-[var(--line)] text-[var(--slate)]",
  uncollectible: "border-[var(--danger)] text-[var(--danger)]",
  void: "border-[var(--line)] text-[var(--slate)]",
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "border-[var(--line)] text-[var(--slate)]";
  return <Stamp className={style}>{status}</Stamp>;
}

function InvoiceRow({ invoice }: { invoice: Invoice }) {
  return (
    <tr
      data-testid="invoices-row"
      data-id={invoice.id}
      className="h-10 border-t border-[var(--line)] font-[family-name:var(--font-mono)] text-[13px] tabular-nums"
    >
      <td className="px-4 py-2 text-[var(--ink)]">
        {new Date(invoice.created).toLocaleDateString()}
      </td>
      <td className="px-4 py-2 text-[var(--slate)]">{invoice.number ?? "—"}</td>
      <td className="px-4 py-2 font-medium text-[var(--ink)]">
        {formatMoney(invoice.amount_due, { currency: invoice.currency })}
      </td>
      <td className="px-4 py-2">
        <StatusBadge status={invoice.status} />
      </td>
      <td className="px-4 py-2 text-right">
        <span className="inline-flex gap-3">
          {invoice.hosted_invoice_url && (
            <a
              data-testid="invoices-view-button"
              href={invoice.hosted_invoice_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-[var(--teal-deep)] hover:text-[var(--teal)]"
            >
              View
            </a>
          )}
          {invoice.invoice_pdf && (
            <a
              data-testid="invoices-pdf-button"
              href={invoice.invoice_pdf}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-[var(--teal-deep)] hover:text-[var(--teal)]"
            >
              PDF
            </a>
          )}
        </span>
      </td>
    </tr>
  );
}

// Invoice history, rendered on the billing page for admins/owners only.
export default function InvoicesSection({ orgId, enabled }: InvoicesSectionProps) {
  const { data: invoices, isLoading, error } = useInvoices(orgId, enabled);

  return (
    <section data-testid="billing-invoices" className="mt-12" aria-label="Invoices">
      <SectionRule index="05" title="Invoices" />
      {isLoading && (
        <div data-testid="invoices-loading" className="mt-4 flex justify-center">
          <Spinner className="h-5 w-5" />
        </div>
      )}
      <ErrorAlert error={error} className="mt-4" data-testid="invoices-error" />
      {invoices && invoices.length === 0 && (
        <div
          data-testid="invoices-empty"
          className="mt-3 rounded border border-dashed border-[var(--line)] px-5 py-6 text-center"
        >
          <p className="text-sm text-[var(--ink)]">No invoices yet.</p>
          <p className="mt-1 text-xs text-[var(--slate)]">
            Receipts for plans and credit packs appear here after your first payment.
          </p>
        </div>
      )}
      {invoices && invoices.length > 0 && (
        <div className="mt-3 overflow-x-auto rounded border border-[var(--line)] bg-white">
          <table data-testid="invoices-table" className="w-full text-left">
            <thead>
              <tr className="h-10 bg-[var(--mist)] font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-normal text-[var(--slate)]">
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Number</th>
                <th className="px-4 py-2 font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">Links</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => (
                <InvoiceRow key={invoice.id} invoice={invoice} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
