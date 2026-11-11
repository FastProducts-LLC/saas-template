import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Markdown, { sanitizeUrl } from "./markdown";

describe("Markdown renderer", () => {
  it("renders headings, lists, and fenced code", () => {
    const { container } = render(
      <Markdown content={"## Section\n\nA paragraph.\n\n- one\n- two\n\n```\nconst x = 1;\n```"} />,
    );
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Section");
    expect(screen.getByText("A paragraph.")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(container.querySelector("pre code")).toHaveTextContent("const x = 1;");
  });

  it("renders bold, italic, inline code, and safe links", () => {
    render(<Markdown content={"**bold** *ital* `code` [site](https://example.com)"} />);
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByText("ital").tagName).toBe("EM");
    expect(screen.getByText("code").tagName).toBe("CODE");
    const link = screen.getByRole("link", { name: "site" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("neutralizes javascript: URLs", () => {
    render(<Markdown content={"[click](javascript:alert(1))"} />);
    expect(screen.getByRole("link", { name: "click" })).toHaveAttribute("href", "#");
  });

  it("renders raw HTML as text, not markup", () => {
    const { container } = render(<Markdown content={'<script>alert("xss")</script>'} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain('<script>alert("xss")</script>');
  });
});

describe("sanitizeUrl", () => {
  it("allows http(s), mailto, relative, and anchors", () => {
    expect(sanitizeUrl("https://a.com/x")).toBe("https://a.com/x");
    expect(sanitizeUrl("http://a.com")).toBe("http://a.com");
    expect(sanitizeUrl("mailto:a@b.com")).toBe("mailto:a@b.com");
    expect(sanitizeUrl("/blog/post")).toBe("/blog/post");
    expect(sanitizeUrl("#section")).toBe("#section");
  });

  it("blocks script and data schemes", () => {
    expect(sanitizeUrl("javascript:alert(1)")).toBe("#");
    expect(sanitizeUrl(" JaVaScRiPt:alert(1)")).toBe("#");
    expect(sanitizeUrl("data:text/html,<b>x</b>")).toBe("#");
  });
});
