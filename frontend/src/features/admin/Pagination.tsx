// Prev/next pager for the admin tables, driven by the backend Page envelope.

import type { Page } from "./api";

interface Props {
  page: Page<unknown>;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, onPageChange }: Props) {
  const lastPage = Math.max(1, Math.ceil(page.total / page.page_size));
  const from = page.total === 0 ? 0 : (page.page - 1) * page.page_size + 1;
  const to = Math.min(page.page * page.page_size, page.total);

  return (
    <div className="flex items-center justify-between border-t border-[var(--mist)] px-4 py-2 text-sm text-[var(--slate)]/75">
      <span data-testid="pagination-info">
        {from}–{to} of {page.total}
      </span>
      <div className="flex gap-2">
        <button
          data-testid="pagination-prev-button"
          onClick={() => onPageChange(page.page - 1)}
          disabled={page.page <= 1}
          className="rounded-md border border-[var(--slate)]/25 px-2 py-1 hover:bg-[var(--paper)] disabled:opacity-50"
        >
          Previous
        </button>
        <button
          data-testid="pagination-next-button"
          onClick={() => onPageChange(page.page + 1)}
          disabled={page.page >= lastPage}
          className="rounded-md border border-[var(--slate)]/25 px-2 py-1 hover:bg-[var(--paper)] disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
