import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearEditorDraft,
  editorDraftKey,
  isDraftNewerThan,
  loadEditorDraft,
  saveEditorDraft,
  type EditorDraft,
} from "./autosave";

const draft: EditorDraft = {
  title: "Hello",
  slug: "hello",
  slugTouched: true,
  tagsInput: "a, b",
  excerpt: "Excerpt",
  content: "Body",
  coverImage: "",
  metaTitle: "",
  metaDescription: "",
  scheduleValue: "",
  saved_at: "2026-08-07T12:00:00.000Z",
};

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("editorDraftKey", () => {
  it("scopes by post id or 'new'", () => {
    expect(editorDraftKey("new")).toBe("blog:editor:new");
    expect(editorDraftKey("abc")).toBe("blog:editor:abc");
  });
});

describe("save/load/clear", () => {
  it("roundtrips a draft", () => {
    const key = editorDraftKey("new");
    saveEditorDraft(key, draft);
    expect(loadEditorDraft(key)).toEqual(draft);
  });

  it("clear removes the draft", () => {
    const key = editorDraftKey("new");
    saveEditorDraft(key, draft);
    clearEditorDraft(key);
    expect(loadEditorDraft(key)).toBeNull();
  });

  it("returns null for corrupted JSON", () => {
    const key = editorDraftKey("new");
    localStorage.setItem(key, "{not-json");
    expect(loadEditorDraft(key)).toBeNull();
  });

  it("returns null for non-object JSON", () => {
    const key = editorDraftKey("new");
    localStorage.setItem(key, '"just a string"');
    expect(loadEditorDraft(key)).toBeNull();
  });
});

describe("isDraftNewerThan", () => {
  it("compares saved_at against post updated_at", () => {
    expect(isDraftNewerThan(draft, "2026-08-07T11:00:00.000Z")).toBe(true);
    expect(isDraftNewerThan(draft, "2026-08-07T13:00:00.000Z")).toBe(false);
    expect(isDraftNewerThan(draft, "2026-08-07T12:00:00.000Z")).toBe(false);
  });
});
