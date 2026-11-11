// Create/edit form for one blog post — serves /admin/blog/new (no :id param)
// and /admin/blog/:id. Markdown content with a write/preview toggle; slug
// auto-fills from the title until manually edited. Local drafts autosave to
// localStorage (see model/autosave.ts) with an opt-in restore banner.

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { isApiErrorWithCode } from "../../../shared/api";
import Markdown from "../../../shared/lib/markdown";
import {
  BLOG_COVER_IMAGE_URL_MAX_LENGTH,
  BLOG_EXCERPT_MAX_LENGTH,
  BLOG_META_DESCRIPTION_MAX_LENGTH,
  BLOG_META_TITLE_MAX_LENGTH,
  BLOG_SLUG_MAX_LENGTH,
  BLOG_TITLE_MAX_LENGTH,
} from "../../../shared/lib/policy";
import { relativeTime } from "../../../shared/lib/time";
import { Alert, Button, Input, Modal, Spinner, Stamp, ErrorAlert } from "../../../shared/ui";
import * as endpoints from "../api/endpoints";
import { useAdminPost, useCreatePost, useDeletePost, useUpdatePost } from "../api/hooks";
import {
  clearEditorDraft,
  editorDraftKey,
  isDraftNewerThan,
  loadEditorDraft,
  saveEditorDraft,
  type EditorDraft,
} from "../model/autosave";
import { parseTagsInput, slugify, type PostStatus } from "../model/types";

const TEXTAREA_CLASS =
  "w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15";

const INPUT_CLASS =
  "w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15";

const statusTones: Record<PostStatus, string> = {
  draft: "border-[var(--info)] text-[var(--info)]",
  published: "border-[var(--success)] text-[var(--success)]",
  archived: "border-[var(--slate)]/40 text-[var(--slate)]",
  scheduled: "border-[var(--info)] text-[var(--info)]",
};

/** Format a Date for `<input type="datetime-local">` (local wall clock). */
function toLocalDatetimeValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AdminBlogEditorPage() {
  const { id } = useParams();
  const isNew = !id;
  const navigate = useNavigate();
  const draftKey = editorDraftKey(isNew ? "new" : id!);

  const { data: post, isLoading } = useAdminPost(id);
  const create = useCreatePost();
  const update = useUpdatePost(id ?? "");
  const remove = useDeletePost();

  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [tagsInput, setTagsInput] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [content, setContent] = useState("");
  const [coverImage, setCoverImage] = useState("");
  const [metaTitle, setMetaTitle] = useState("");
  const [metaDescription, setMetaDescription] = useState("");
  const [preview, setPreview] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [saved, setSaved] = useState(false);
  const [scheduleValue, setScheduleValue] = useState("");
  const [pendingDraft, setPendingDraft] = useState<EditorDraft | null>(null);
  const [previewCopied, setPreviewCopied] = useState(false);
  const [previewLinkBusy, setPreviewLinkBusy] = useState(false);

  // Skip debounced autosave until the form has been hydrated from the server
  // (or, for new posts, until the restore check has run).
  const hydratedRef = useRef(false);
  const restoreCheckedRef = useRef(false);

  const applyDraft = (draft: EditorDraft) => {
    setTitle(draft.title);
    setSlug(draft.slug);
    setSlugTouched(draft.slugTouched);
    setTagsInput(draft.tagsInput);
    setExcerpt(draft.excerpt);
    setContent(draft.content);
    setCoverImage(draft.coverImage);
    setMetaTitle(draft.metaTitle);
    setMetaDescription(draft.metaDescription);
    setScheduleValue(draft.scheduleValue);
  };

  // Hydrate the form when an existing post loads; offer restore if a newer
  // local draft exists.
  useEffect(() => {
    if (isNew) {
      if (restoreCheckedRef.current) return;
      restoreCheckedRef.current = true;
      const stored = loadEditorDraft(draftKey);
      // One-time hydration from localStorage, guarded by restoreCheckedRef.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (stored) setPendingDraft(stored);
      hydratedRef.current = true;
      return;
    }
    if (!post) return;
    setTitle(post.title);
    setSlug(post.slug);
    setSlugTouched(true);
    setTagsInput(post.tags.join(", "));
    setExcerpt(post.excerpt);
    setContent(post.content);
    setCoverImage(post.cover_image ?? "");
    setMetaTitle(post.meta_title ?? "");
    setMetaDescription(post.meta_description ?? "");

    if (!restoreCheckedRef.current) {
      restoreCheckedRef.current = true;
      const stored = loadEditorDraft(draftKey);
      if (stored && isDraftNewerThan(stored, post.updated_at)) {
        setPendingDraft(stored);
      }
    }
    hydratedRef.current = true;
  }, [post, isNew, draftKey]);

  // Debounced (1s) autosave after hydration whenever form fields change.
  // Skip while a restore banner is up so we don't overwrite the stored draft.
  useEffect(() => {
    if (!hydratedRef.current || pendingDraft) return;
    const handle = window.setTimeout(() => {
      saveEditorDraft(draftKey, {
        title,
        slug,
        slugTouched,
        tagsInput,
        excerpt,
        content,
        coverImage,
        metaTitle,
        metaDescription,
        scheduleValue,
        saved_at: new Date().toISOString(),
      });
    }, 1000);
    return () => window.clearTimeout(handle);
  }, [
    title,
    slug,
    slugTouched,
    tagsInput,
    excerpt,
    content,
    coverImage,
    metaTitle,
    metaDescription,
    scheduleValue,
    draftKey,
    pendingDraft,
  ]);

  const parsedTags = parseTagsInput(tagsInput);
  const mutationError = create.error ?? update.error;
  const slugError = isApiErrorWithCode(mutationError, "ERR_BLOG_002")
    ? mutationError.userMessage
    : undefined;
  const busy = create.isPending || update.isPending;

  const scheduleAt = scheduleValue ? new Date(scheduleValue) : null;
  const canSchedule =
    scheduleAt != null &&
    !Number.isNaN(scheduleAt.getTime()) &&
    // A UI hint re-evaluated every render; the server re-validates the time.
    // eslint-disable-next-line react-hooks/purity
    scheduleAt.getTime() > Date.now();

  const payload = () => ({
    title,
    slug: slug.trim() || null,
    excerpt,
    content,
    cover_image: coverImage.trim() || null,
    meta_title: metaTitle.trim() || null,
    meta_description: metaDescription.trim() || null,
    tags: parseTagsInput(tagsInput),
  });

  const flashSaved = () => {
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
  };

  const clearDraft = () => {
    clearEditorDraft(draftKey);
    setPendingDraft(null);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (isNew) {
      create.mutate(
        { ...payload(), status: "draft" },
        {
          onSuccess: (created) => {
            clearDraft();
            navigate(ROUTES.admin.blogPost(created.id), { replace: true });
          },
        },
      );
    } else {
      update.mutate(payload(), {
        onSuccess: () => {
          clearDraft();
          flashSaved();
        },
      });
    }
  };

  const setStatus = (status: PostStatus) => {
    if (isNew) {
      create.mutate(
        { ...payload(), status },
        {
          onSuccess: (created) => {
            clearDraft();
            navigate(ROUTES.admin.blogPost(created.id), { replace: true });
          },
        },
      );
    } else {
      update.mutate(
        { ...payload(), status },
        {
          onSuccess: () => {
            clearDraft();
            flashSaved();
          },
        },
      );
    }
  };

  const handleSchedule = () => {
    if (!canSchedule || scheduleAt == null) return;
    update.mutate(
      {
        status: "scheduled" as PostStatus,
        scheduled_for: scheduleAt.toISOString(),
      },
      {
        onSuccess: () => {
          clearDraft();
          flashSaved();
        },
      },
    );
  };

  const handleCopyPreviewLink = async () => {
    if (!id || previewLinkBusy) return;
    setPreviewLinkBusy(true);
    try {
      const { url } = await endpoints.createPreviewLink(id);
      await navigator.clipboard.writeText(url);
      setPreviewCopied(true);
      window.setTimeout(() => setPreviewCopied(false), 2000);
    } catch {
      // Clipboard / network failure — leave the button idle; mutation errors
      // elsewhere already surface via Alert.
    } finally {
      setPreviewLinkBusy(false);
    }
  };

  if (!isNew && isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  }

  const currentStatus: PostStatus = post?.status ?? "draft";
  const isScheduled = currentStatus === ("scheduled" as PostStatus);
  const canOfferSchedule = !isNew && (currentStatus === "draft" || currentStatus === "archived");

  return (
    <div data-testid="admin-blog-editor-page" className="max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            to={ROUTES.admin.blog}
            data-testid="admin-blog-back-link"
            className="text-sm font-medium text-[var(--teal-deep)] hover:underline"
          >
            ← All posts
          </Link>
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
            {isNew ? "New post" : "Edit post"}
          </h2>
          {!isNew && <Stamp className={statusTones[currentStatus]}>{currentStatus}</Stamp>}
        </div>
        {!isNew && post && (
          <div className="flex flex-wrap items-center gap-3">
            <a
              href={ROUTES.blog.post(post.slug)}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="admin-blog-view-link"
              className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)] hover:text-[var(--ink)]"
            >
              /blog/{post.slug} ↗
            </a>
            <Button
              type="button"
              variant="secondary"
              data-testid="admin-blog-preview-link-button"
              loading={previewLinkBusy}
              onClick={() => void handleCopyPreviewLink()}
            >
              Copy preview link
            </Button>
            {previewCopied && (
              <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]">
                Copied
              </span>
            )}
          </div>
        )}
      </div>

      {pendingDraft && (
        <div className="mt-4" data-testid="admin-blog-restore-banner">
          <Alert tone="info">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>You have unsaved changes from {relativeTime(pendingDraft.saved_at)}.</span>
              <span className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  data-testid="admin-blog-restore-button"
                  onClick={() => {
                    applyDraft(pendingDraft);
                    setPendingDraft(null);
                  }}
                >
                  Restore
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  data-testid="admin-blog-discard-button"
                  onClick={clearDraft}
                >
                  Discard
                </Button>
              </span>
            </div>
          </Alert>
        </div>
      )}

      {saved && (
        <div className="mt-4">
          <Alert tone="success">Saved.</Alert>
        </div>
      )}
      {mutationError != null && slugError === undefined && (
        <div className="mt-4">
          <ErrorAlert error={mutationError} />
        </div>
      )}
      {remove.error != null && (
        <div className="mt-4">
          <ErrorAlert error={remove.error} />
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <Input
          label="Title"
          data-testid="admin-blog-title-input"
          required
          value={title}
          maxLength={BLOG_TITLE_MAX_LENGTH}
          onChange={(e) => {
            setTitle(e.target.value);
            if (!slugTouched) setSlug(slugify(e.target.value));
          }}
        />

        <div>
          <Input
            label="Slug"
            data-testid="admin-blog-slug-input"
            value={slug}
            maxLength={BLOG_SLUG_MAX_LENGTH}
            error={slugError}
            onChange={(e) => {
              setSlugTouched(true);
              setSlug(e.target.value);
            }}
          />
          {currentStatus === "published" && post && slug !== post.slug && (
            <p className="mt-1 text-sm text-[var(--danger)]">
              Changing the slug changes the public URL — old links will 404.
            </p>
          )}
        </div>

        <div>
          <Input
            label="Tags"
            data-testid="admin-blog-tags-input"
            value={tagsInput}
            placeholder="product, launch, engineering"
            onChange={(e) => setTagsInput(e.target.value)}
          />
          <p className="mt-1 text-xs text-[var(--slate)]/60">Up to 5, comma-separated</p>
          {parsedTags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {parsedTags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-[var(--line)] px-2 py-0.5 font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--slate)]">Excerpt</label>
          <textarea
            data-testid="admin-blog-excerpt-input"
            required
            rows={2}
            value={excerpt}
            maxLength={BLOG_EXCERPT_MAX_LENGTH}
            onChange={(e) => setExcerpt(e.target.value)}
            className={TEXTAREA_CLASS}
          />
          <p className="mt-1 text-right text-xs text-[var(--slate)]/50">
            {excerpt.length}/{BLOG_EXCERPT_MAX_LENGTH}
          </p>
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="block text-sm font-medium text-[var(--slate)]">
              Content (markdown)
            </label>
            <div className="flex gap-1 text-xs">
              <button
                type="button"
                data-testid="admin-blog-write-tab"
                onClick={() => setPreview(false)}
                className={`rounded px-2 py-1 font-medium ${
                  preview
                    ? "text-[var(--slate)] hover:text-[var(--ink)]"
                    : "bg-[var(--mist)] text-[var(--ink)]"
                }`}
              >
                Write
              </button>
              <button
                type="button"
                data-testid="admin-blog-preview-tab"
                onClick={() => setPreview(true)}
                className={`rounded px-2 py-1 font-medium ${
                  preview
                    ? "bg-[var(--mist)] text-[var(--ink)]"
                    : "text-[var(--slate)] hover:text-[var(--ink)]"
                }`}
              >
                Preview
              </button>
            </div>
          </div>
          {preview ? (
            <div
              data-testid="admin-blog-preview"
              className="blog-prose min-h-[20rem] rounded border border-[var(--line)] bg-white px-4 py-3"
            >
              <Markdown content={content} />
            </div>
          ) : (
            <textarea
              data-testid="admin-blog-content-input"
              required
              rows={16}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={"## Heading\n\nWrite markdown here — blank line between paragraphs."}
              className={`${TEXTAREA_CLASS} font-[family-name:var(--font-mono)] text-[13px] leading-relaxed`}
            />
          )}
        </div>

        <Input
          label="Cover image URL (optional)"
          data-testid="admin-blog-cover-input"
          type="url"
          placeholder="https://…"
          value={coverImage}
          maxLength={BLOG_COVER_IMAGE_URL_MAX_LENGTH}
          onChange={(e) => setCoverImage(e.target.value)}
        />

        <details className="rounded border border-[var(--line)] bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-[var(--slate)]">
            SEO overrides
          </summary>
          <div className="mt-4 space-y-4">
            <Input
              label={`Meta title (defaults to the post title, max ${BLOG_META_TITLE_MAX_LENGTH})`}
              data-testid="admin-blog-meta-title-input"
              value={metaTitle}
              maxLength={BLOG_META_TITLE_MAX_LENGTH}
              onChange={(e) => setMetaTitle(e.target.value)}
            />
            <div>
              <label className="mb-1 block text-sm font-medium text-[var(--slate)]">
                Meta description
              </label>
              <textarea
                data-testid="admin-blog-meta-description-input"
                rows={2}
                value={metaDescription}
                maxLength={BLOG_META_DESCRIPTION_MAX_LENGTH}
                onChange={(e) => setMetaDescription(e.target.value)}
                className={TEXTAREA_CLASS}
              />
              <p className="mt-1 text-right text-xs text-[var(--slate)]/50">
                {metaDescription.length}/{BLOG_META_DESCRIPTION_MAX_LENGTH}
              </p>
            </div>
          </div>
        </details>

        <div className="flex flex-wrap items-center gap-3 border-t border-[var(--line)] pt-5">
          <Button type="submit" data-testid="admin-blog-save-button" loading={busy}>
            {isNew ? "Save draft" : "Save changes"}
          </Button>
          {(isNew || (currentStatus !== "published" && !isScheduled)) && (
            <Button
              type="button"
              variant="secondary"
              data-testid="admin-blog-publish-button"
              loading={busy}
              onClick={() => setStatus("published")}
            >
              {isNew ? "Save & publish" : "Publish"}
            </Button>
          )}
          {isScheduled && post && (
            <>
              <p
                data-testid="admin-blog-scheduled-at"
                className="font-[family-name:var(--font-mono)] text-sm text-[var(--slate)]"
              >
                Scheduled for{" "}
                {post.published_at ? new Date(post.published_at).toLocaleString() : "—"}
              </p>
              <Button
                type="button"
                variant="secondary"
                data-testid="admin-blog-publish-now-button"
                loading={busy}
                onClick={() => setStatus("published")}
              >
                Publish now
              </Button>
              <Button
                type="button"
                variant="secondary"
                data-testid="admin-blog-unschedule-button"
                loading={busy}
                onClick={() => setStatus("draft")}
              >
                Unschedule
              </Button>
            </>
          )}
          {!isNew && currentStatus === "published" && (
            <>
              <Button
                type="button"
                variant="secondary"
                data-testid="admin-blog-unpublish-button"
                loading={busy}
                onClick={() => setStatus("draft")}
              >
                Unpublish
              </Button>
              <Button
                type="button"
                variant="secondary"
                data-testid="admin-blog-archive-button"
                loading={busy}
                onClick={() => setStatus("archived")}
              >
                Archive
              </Button>
            </>
          )}
          {!isNew && (
            <button
              type="button"
              data-testid="admin-blog-delete-button"
              onClick={() => setConfirmDelete(true)}
              className="ml-auto text-sm font-medium text-[var(--danger)] hover:underline"
            >
              Delete
            </button>
          )}
        </div>

        {canOfferSchedule && (
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[14rem] flex-1">
              <label
                htmlFor="admin-blog-schedule-input"
                className="mb-1 block text-sm font-medium text-[var(--slate)]"
              >
                Schedule for
              </label>
              <input
                id="admin-blog-schedule-input"
                type="datetime-local"
                data-testid="admin-blog-schedule-input"
                min={toLocalDatetimeValue(new Date())}
                value={scheduleValue}
                onChange={(e) => setScheduleValue(e.target.value)}
                className={INPUT_CLASS}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              data-testid="admin-blog-schedule-button"
              loading={busy}
              disabled={!canSchedule}
              onClick={handleSchedule}
            >
              Schedule
            </Button>
          </div>
        )}
      </form>

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete this post?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="danger-confirm"
              data-testid="admin-blog-confirm-delete-button"
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(id!, {
                  onSuccess: () => {
                    clearDraft();
                    navigate(ROUTES.admin.blog);
                  },
                  onSettled: () => setConfirmDelete(false),
                })
              }
            >
              Delete permanently
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--slate)]">
          This permanently deletes “{post?.title}”. If you just want it off the public blog, archive
          it instead.
        </p>
      </Modal>
    </div>
  );
}
