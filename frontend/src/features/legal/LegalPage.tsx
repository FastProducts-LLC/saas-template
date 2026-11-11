// Public legal pages, rendered from the markdown files in this folder.
//
// Configure identity in shared/brand.toml ([brand], [deploy], [legal]), then
// run python3 scripts/gen_brand.py to regenerate the placeholder values. The
// renderer below intentionally supports only the subset these documents use
// (#/##/### headings, paragraphs, **bold**, [links](...), - bullet lists);
// swap it for react-markdown if you need full markdown.

import { type JSX } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../shared/lib/routes";
import { fillLegalPlaceholders } from "./model/placeholders";

function renderInline(text: string): (string | JSX.Element)[] {
  // Split on **bold** and [label](href), keeping delimiters.
  return text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).map((part, i) => {
    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold) return <strong key={i}>{bold[1]}</strong>;
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      return (
        <a key={i} href={link[2]} className="text-[var(--teal-deep)] hover:underline">
          {link[1]}
        </a>
      );
    }
    return part;
  });
}

function renderMarkdown(markdown: string): JSX.Element[] {
  // Drop the HTML comment config block, then walk line-by-line.
  const lines = fillLegalPlaceholders(markdown.replace(/<!--[\s\S]*?-->/g, "")).split("\n");
  const blocks: JSX.Element[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];

  const flush = () => {
    if (paragraph.length) {
      blocks.push(
        <p key={blocks.length} className="mt-4 text-sm leading-6 text-[var(--slate)]">
          {renderInline(paragraph.join(" "))}
        </p>,
      );
      paragraph = [];
    }
    if (list.length) {
      blocks.push(
        <ul
          key={blocks.length}
          className="mt-4 list-disc space-y-1 pl-6 text-sm leading-6 text-[var(--slate)]"
        >
          {list.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flush();
    } else if (trimmed.startsWith("### ")) {
      flush();
      blocks.push(
        <h3 key={blocks.length} className="mt-6 text-base font-semibold text-[var(--ink)]">
          {renderInline(trimmed.slice(4))}
        </h3>,
      );
    } else if (trimmed.startsWith("## ")) {
      flush();
      blocks.push(
        <h2
          key={blocks.length}
          className="mt-8 font-[family-name:var(--font-display)] text-lg font-semibold text-[var(--ink)]"
        >
          {renderInline(trimmed.slice(3))}
        </h2>,
      );
    } else if (trimmed.startsWith("# ")) {
      flush();
      blocks.push(
        <h1
          key={blocks.length}
          className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[var(--ink)]"
        >
          {trimmed.slice(2)}
        </h1>,
      );
    } else if (trimmed.startsWith("- ")) {
      if (paragraph.length) flush();
      list.push(trimmed.slice(2));
    } else {
      if (list.length) flush();
      paragraph.push(trimmed);
    }
  }
  flush();
  return blocks;
}

export default function LegalPage({
  markdown,
  "data-testid": testId,
}: {
  markdown: string;
  "data-testid"?: string;
}) {
  return (
    <div className="min-h-screen bg-[var(--paper)] px-4 py-12" data-testid={testId}>
      <div className="mx-auto max-w-3xl rounded-2xl border border-[var(--mist)] bg-white p-8 shadow-xl shadow-[color-mix(in_srgb,var(--ink)_6%,transparent)] sm:p-12">
        <article>{renderMarkdown(markdown)}</article>
        <div className="mt-10 border-t border-[var(--mist)] pt-6">
          <Link
            to={ROUTES.home}
            className="text-sm text-[var(--teal-deep)] hover:underline"
            data-testid="legal-back-link"
          >
            &larr; Back to app
          </Link>
        </div>
      </div>
    </div>
  );
}
