import React from "react";

/**
 * Zero-dependency, XSS-safe Markdown renderer.
 *
 * Covers the common authoring subset: headings, ordered/unordered lists,
 * blockquotes, fenced code, bold/italic/inline-code, links, horizontal rules.
 * Builds React nodes directly (no dangerouslySetInnerHTML) and sanitizes link
 * hrefs to http(s)/mailto/relative/anchor only.
 *
 * NOTE: parsing is LINE-BASED — real newlines separate blocks (blank line
 * between paragraphs, each heading/list item on its own line). Content pasted
 * as one long line renders as a single paragraph.
 *
 * Emits plain semantic elements (<h2>, <p>, <ul>, ...). Wrap the output in a
 * styled container (e.g. <div className="blog-prose">) — under the Tailwind
 * reset, unstyled headings/paragraphs collapse to body text.
 */

export function sanitizeUrl(url: string): string {
  const trimmed = url.trim();
  // Allow http(s), mailto, root-relative, and in-page anchors only.
  if (/^(https?:\/\/|mailto:|\/|#)/i.test(trimmed)) return trimmed;
  return "#";
}

const INLINE_PATTERNS: {
  re: RegExp;
  render: (m: RegExpMatchArray, key: string) => React.ReactNode;
}[] = [
  { re: /\*\*([^*]+)\*\*/, render: (m, k) => <strong key={k}>{renderInline(m[1], k)}</strong> },
  { re: /__([^_]+)__/, render: (m, k) => <strong key={k}>{renderInline(m[1], k)}</strong> },
  {
    re: /(?<![*\w])\*([^*\n]+)\*(?![*\w])/,
    render: (m, k) => <em key={k}>{renderInline(m[1], k)}</em>,
  },
  { re: /`([^`]+)`/, render: (m, k) => <code key={k}>{m[1]}</code> },
  {
    re: /\[([^\]]+)\]\(([^)\s]+)\)/,
    render: (m, k) => (
      <a key={k} href={sanitizeUrl(m[2])} target="_blank" rel="noopener noreferrer">
        {m[1]}
      </a>
    ),
  },
];

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let remaining = text;
  let counter = 0;

  while (remaining.length > 0) {
    let earliest: { idx: number; len: number; node: React.ReactNode } | null = null;
    for (const p of INLINE_PATTERNS) {
      const m = remaining.match(p.re);
      if (m && m.index !== undefined) {
        if (earliest === null || m.index < earliest.idx) {
          earliest = {
            idx: m.index,
            len: m[0].length,
            node: p.render(m, `${keyPrefix}-${counter}`),
          };
        }
      }
    }
    if (earliest === null) {
      nodes.push(remaining);
      break;
    }
    if (earliest.idx > 0) nodes.push(remaining.slice(0, earliest.idx));
    nodes.push(earliest.node);
    remaining = remaining.slice(earliest.idx + earliest.len);
    counter += 1;
  }
  return nodes;
}

const isHr = (l: string) => /^\s*([-*_])(\s*\1){2,}\s*$/.test(l);
const isUl = (l: string) => /^\s*[-*+]\s+/.test(l);
const isOl = (l: string) => /^\s*\d+\.\s+/.test(l);
const isHeading = (l: string) => /^#{1,6}\s+/.test(l);
const isQuote = (l: string) => l.trim().startsWith(">");
const isFence = (l: string) => l.trim().startsWith("```");

export function Markdown({ content }: { content: string }) {
  const lines = (content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (isFence(line)) {
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !isFence(lines[i])) buf.push(lines[i++]);
      i += 1; // consume closing fence
      blocks.push(
        <pre key={key++}>
          <code>{buf.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    if (line.trim() === "") {
      i += 1;
      continue;
    }

    if (isHr(line)) {
      blocks.push(<hr key={key++} />);
      i += 1;
      continue;
    }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const level = Math.min(h[1].length, 6);
      const Tag = `h${level}` as keyof React.JSX.IntrinsicElements;
      blocks.push(<Tag key={key++}>{renderInline(h[2].trim(), `h-${key}`)}</Tag>);
      i += 1;
      continue;
    }

    if (isQuote(line)) {
      const buf: string[] = [];
      while (i < lines.length && isQuote(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      blocks.push(<blockquote key={key++}>{renderInline(buf.join(" "), `bq-${key}`)}</blockquote>);
      continue;
    }

    if (isUl(line)) {
      const items: string[] = [];
      while (i < lines.length && isUl(lines[i])) items.push(lines[i++].replace(/^\s*[-*+]\s+/, ""));
      blocks.push(
        <ul key={key++}>
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it, `ul-${key}-${idx}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (isOl(line)) {
      const items: string[] = [];
      while (i < lines.length && isOl(lines[i])) items.push(lines[i++].replace(/^\s*\d+\.\s+/, ""));
      blocks.push(
        <ol key={key++}>
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it, `ol-${key}-${idx}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    // Paragraph: gather consecutive non-block lines.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !isHeading(lines[i]) &&
      !isFence(lines[i]) &&
      !isQuote(lines[i]) &&
      !isUl(lines[i]) &&
      !isOl(lines[i]) &&
      !isHr(lines[i])
    ) {
      para.push(lines[i++]);
    }
    blocks.push(<p key={key++}>{renderInline(para.join(" "), `p-${key}`)}</p>);
  }

  return <>{blocks}</>;
}

export default Markdown;
