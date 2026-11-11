import { expect, request } from "@playwright/test";

const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? "http://localhost:21431";

interface MailpitSearchResult {
  messages: Array<{ ID: string; To: Array<{ Address: string }>; Subject: string }>;
}

// Poll Mailpit for the newest message to `recipient` (optionally filtered by
// subject substring) and return its HTML body.
export async function fetchEmailHtml(recipient: string, subjectContains?: string): Promise<string> {
  const api = await request.newContext({ baseURL: MAILPIT_URL });
  try {
    let messageId: string | undefined;
    await expect
      .poll(
        async () => {
          const query = subjectContains
            ? `to:"${recipient}" subject:"${subjectContains}"`
            : `to:"${recipient}"`;
          const res = await api.get(`/api/v1/search?query=${encodeURIComponent(query)}&limit=5`);
          if (!res.ok()) return 0;
          const data = (await res.json()) as MailpitSearchResult;
          messageId = data.messages[0]?.ID;
          return data.messages.length;
        },
        { message: `email to ${recipient} to arrive in Mailpit`, timeout: 15_000 },
      )
      .toBeGreaterThan(0);

    const res = await api.get(`/api/v1/message/${messageId}`);
    expect(res.ok()).toBe(true);
    const body = (await res.json()) as { HTML: string; Text: string };
    return body.HTML || body.Text;
  } finally {
    await api.dispose();
  }
}

// Extract the first app link whose path starts with `path` (e.g. "/verify-email").
export function extractAppLink(html: string, path: string): string {
  const unescaped = html.replace(/&amp;/g, "&").replace(/=\r?\n/g, "");
  const match = unescaped.match(new RegExp(`https?://[^"'\\s>]+${path}[^"'\\s>]*`));
  if (!match) throw new Error(`no link containing ${path} found in email`);
  return match[0];
}
