// localStorage-backed editor drafts. Components never touch localStorage
// directly — only these helpers do (and they silently no-op on failure,
// e.g. private browsing).

export interface EditorDraft {
  title: string;
  slug: string;
  slugTouched: boolean;
  tagsInput: string;
  excerpt: string;
  content: string;
  coverImage: string;
  metaTitle: string;
  metaDescription: string;
  scheduleValue: string;
  saved_at: string;
}

export function editorDraftKey(postId: string | "new"): string {
  return `blog:editor:${postId}`;
}

export function saveEditorDraft(key: string, draft: EditorDraft): void {
  try {
    localStorage.setItem(key, JSON.stringify(draft));
  } catch {
    // private browsing / quota — ignore
  }
}

export function loadEditorDraft(key: string): EditorDraft | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    const d = parsed as Partial<EditorDraft>;
    if (typeof d.saved_at !== "string" || typeof d.title !== "string") return null;
    return d as EditorDraft;
  } catch {
    return null;
  }
}

export function clearEditorDraft(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

/** True when the local draft is newer than the server post's updated_at. */
export function isDraftNewerThan(draft: EditorDraft, updatedAt: string): boolean {
  const draftMs = Date.parse(draft.saved_at);
  const serverMs = Date.parse(updatedAt);
  if (Number.isNaN(draftMs) || Number.isNaN(serverMs)) return false;
  return draftMs > serverMs;
}
