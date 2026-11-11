// Public API documentation page.
//
// Source of truth for the prose is `/docs/api.md` in `frontend/public/`
// (also served raw for LLMs and coding tools). This page fetches that
// file at runtime so we never drift from the downloadable markdown.

import { useEffect, useMemo, useState, type JSX, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { MarketingFooter, MarketingHeader } from "../../home";

type Block =
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "p"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "code"; lang: string; code: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "hr" };

function parseInline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).map((part, i) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded bg-[var(--paper)] px-1.5 py-0.5 font-mono text-[0.85em] text-[var(--ink)]"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold) return <strong key={i}>{bold[1]}</strong>;
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const href = link[2];
      const external = href.startsWith("http");
      if (external) {
        return (
          <a
            key={i}
            href={href}
            className="text-[var(--teal-deep)] underline-offset-2 hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            {link[1]}
          </a>
        );
      }
      return (
        <Link
          key={i}
          to={href}
          className="text-[var(--teal-deep)] underline-offset-2 hover:underline"
        >
          {link[1]}
        </Link>
      );
    }
    return part;
  });
}

function parseMarkdown(markdown: string): Block[] {
  const lines = markdown.replace(/^>.*$/gm, (line) => line.replace(/^>\s?/, "")).split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed === "---") {
      blocks.push({ type: "hr" });
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence
      blocks.push({ type: "code", lang, code: codeLines.join("\n") });
      continue;
    }

    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim());
        i += 1;
      }
      const parseRow = (row: string) =>
        row
          .slice(1, -1)
          .split("|")
          .map((c) => c.trim());
      const headers = parseRow(tableLines[0]);
      const bodyStart = tableLines[1]?.includes("---") ? 2 : 1;
      const rows = tableLines.slice(bodyStart).map(parseRow);
      blocks.push({ type: "table", headers, rows });
      continue;
    }

    if (trimmed.startsWith("# ")) {
      blocks.push({ type: "h1", text: trimmed.slice(2) });
      i += 1;
      continue;
    }
    if (trimmed.startsWith("## ")) {
      blocks.push({ type: "h2", text: trimmed.slice(3) });
      i += 1;
      continue;
    }
    if (trimmed.startsWith("### ")) {
      blocks.push({ type: "h3", text: trimmed.slice(4) });
      i += 1;
      continue;
    }

    if (trimmed.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("- ")) {
        items.push(lines[i].trim().slice(2));
        i += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Numbered list → treat as bullets for simplicity
    if (/^\d+\.\s/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s/, ""));
        i += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    const para: string[] = [trimmed];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("#") &&
      !lines[i].trim().startsWith("- ") &&
      !lines[i].trim().startsWith("|") &&
      !lines[i].trim().startsWith("```") &&
      !lines[i].trim().startsWith("---") &&
      !/^\d+\.\s/.test(lines[i].trim())
    ) {
      para.push(lines[i].trim());
      i += 1;
    }
    blocks.push({ type: "p", text: para.join(" ") });
  }

  return blocks;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="group relative mt-4 overflow-hidden rounded-lg border border-[var(--mist)] bg-[var(--ink)]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-white/50">
          {lang || "code"}
        </span>
        <button
          type="button"
          onClick={copy}
          data-testid="api-docs-code-copy"
          className="text-[11px] font-medium text-white/60 transition-colors hover:text-white"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed text-[var(--mist)]">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function renderBlocks(blocks: Block[]): JSX.Element[] {
  return blocks.map((block, idx) => {
    switch (block.type) {
      case "h1":
        return (
          <h1
            key={idx}
            id={slugify(block.text)}
            className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[var(--ink)]"
          >
            {parseInline(block.text)}
          </h1>
        );
      case "h2":
        return (
          <h2
            key={idx}
            id={slugify(block.text)}
            className="mt-10 scroll-mt-28 border-t border-[var(--mist)] pt-8 font-[family-name:var(--font-display)] text-xl font-semibold text-[var(--ink)]"
          >
            {parseInline(block.text)}
          </h2>
        );
      case "h3":
        return (
          <h3
            key={idx}
            id={slugify(block.text)}
            className="mt-6 scroll-mt-28 text-base font-semibold text-[var(--ink)]"
          >
            {parseInline(block.text)}
          </h3>
        );
      case "p":
        return (
          <p key={idx} className="mt-4 text-sm leading-7 text-[var(--slate)]">
            {parseInline(block.text)}
          </p>
        );
      case "ul":
        return (
          <ul
            key={idx}
            className="mt-4 list-disc space-y-1.5 pl-6 text-sm leading-7 text-[var(--slate)]"
          >
            {block.items.map((item, j) => (
              <li key={j}>{parseInline(item)}</li>
            ))}
          </ul>
        );
      case "code":
        return <CodeBlock key={idx} code={block.code} lang={block.lang} />;
      case "table":
        return (
          <div key={idx} className="mt-4 overflow-x-auto rounded-lg border border-[var(--mist)]">
            <table className="w-full min-w-[28rem] text-left text-sm">
              <thead className="bg-[var(--paper)] text-[var(--slate)]">
                <tr>
                  {block.headers.map((h, j) => (
                    <th key={j} className="px-3 py-2 font-medium">
                      {parseInline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, r) => (
                  <tr key={r} className="border-t border-[var(--mist)]">
                    {row.map((cell, c) => (
                      <td key={c} className="px-3 py-2 align-top text-[var(--slate)]">
                        {parseInline(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      case "hr":
        return <hr key={idx} className="my-8 border-[var(--mist)]" />;
      default:
        return <span key={idx} />;
    }
  });
}

export default function ApiDocsPage() {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/docs/api.md")
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load docs (${r.status})`);
        return r.text();
      })
      .then((text) => {
        if (!cancelled) setMarkdown(text);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const blocks = useMemo(() => (markdown ? parseMarkdown(markdown) : []), [markdown]);
  const toc = useMemo(
    () =>
      blocks
        .filter((b): b is Block & { type: "h2"; text: string } => b.type === "h2")
        .map((b) => ({ id: slugify(b.text), label: b.text })),
    [blocks],
  );

  return (
    <div className="min-h-screen bg-[var(--paper)]" data-testid="api-docs-page">
      <MarketingHeader />
      <main className="mx-auto max-w-6xl px-4 pb-20 pt-28 sm:px-6">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-[var(--teal-deep)]">Developers</p>
            <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[var(--ink)] sm:text-4xl">
              API documentation
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--slate)]">
              Authenticate with an org API key and call the credit-metered endpoints. Same content
              is available as plain markdown for LLMs and coding agents.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href="/docs/api.md"
              download="api.md"
              data-testid="api-docs-download-link"
              className="rounded-full border border-[var(--mist)] bg-white px-4 py-2 text-sm font-medium text-[var(--ink)] transition-colors hover:border-[var(--slate)]/30"
            >
              Download api.md
            </a>
            <Link
              to={ROUTES.apiKeys}
              data-testid="api-docs-api-keys-link"
              className="rounded-full bg-[var(--teal)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--teal-deep)]"
            >
              Manage API keys
            </Link>
          </div>
        </div>

        <div className="grid gap-10 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <aside className="hidden lg:block">
            <nav data-testid="api-docs-toc" className="sticky top-28 space-y-1 text-sm">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--slate)]/70">
                On this page
              </p>
              {toc.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  data-testid="api-docs-toc-item"
                  data-id={item.id}
                  className="block rounded-md px-2 py-1.5 text-[var(--slate)] transition-colors hover:bg-white hover:text-[var(--ink)]"
                >
                  {item.label}
                </a>
              ))}
              <div className="mt-6 space-y-2 border-t border-[var(--mist)] pt-4 text-xs text-[var(--slate)]">
                <p className="font-medium text-[var(--ink)]">For AI tools</p>
                <p>
                  Point your agent at{" "}
                  <a
                    href="/docs/api.md"
                    data-testid="api-docs-toc-md-link"
                    className="text-[var(--teal-deep)] hover:underline"
                  >
                    /docs/api.md
                  </a>
                  .
                </p>
              </div>
            </nav>
          </aside>

          <article className="rounded-2xl border border-[var(--mist)] bg-white p-6 shadow-xl shadow-[color-mix(in_srgb,var(--ink)_5%,transparent)] sm:p-10">
            {error && (
              <p data-testid="api-docs-error" className="text-sm text-[var(--danger)]">
                Could not load documentation: {error}
              </p>
            )}
            {!error && !markdown && (
              <p data-testid="api-docs-loading" className="text-sm text-[var(--slate)]/75">
                Loading documentation…
              </p>
            )}
            {markdown && (
              <div data-testid="api-docs-content">
                {/* Skip the duplicate H1 from the markdown — page already has a title */}
                {renderBlocks(blocks.filter((b) => b.type !== "h1"))}
              </div>
            )}
          </article>
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
