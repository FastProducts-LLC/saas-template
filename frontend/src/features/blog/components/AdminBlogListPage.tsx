// Superuser blog console: ledger table of all posts (any status) with a
// status filter. Rendered inside AdminLayout at /admin/blog.

import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { POST_STATUS_VALUES } from "../../../shared/api/enums";
import { Alert, Button, Input, Modal, Spinner, Stamp, ErrorAlert } from "../../../shared/ui";
import { Pagination } from "../../admin";
import { useAdminPosts, useGenerationJob, useRequestDraftGeneration } from "../api/hooks";
import { formatPostDate, parseTagsInput, type LlmProvider, type PostStatus } from "../model/types";

const TEXTAREA_CLASS =
  "w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15";

const statusTones: Record<PostStatus, string> = {
  draft: "border-[var(--info)] text-[var(--info)]",
  published: "border-[var(--success)] text-[var(--success)]",
  archived: "border-[var(--slate)]/40 text-[var(--slate)]",
  scheduled: "border-[var(--info)] text-[var(--info)]",
};

export default function AdminBlogListPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<PostStatus | "">("");
  const [generateOpen, setGenerateOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [notes, setNotes] = useState("");
  const [provider, setProvider] = useState<LlmProvider>("anthropic");
  const [jobId, setJobId] = useState<string | undefined>();
  const [submitError, setSubmitError] = useState<unknown>(null);
  const navigate = useNavigate();
  const { data, isLoading } = useAdminPosts(status, page);
  const requestDraft = useRequestDraftGeneration();
  const jobQuery = useGenerationJob(jobId, { enabled: Boolean(jobId) });

  useEffect(() => {
    const job = jobQuery.data;
    if (!job || job.status !== "succeeded" || !job.post_id) return;
    // Reacting to an external job finishing: close the dialog, then navigate.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setGenerateOpen(false);
    navigate(ROUTES.admin.blogPost(job.post_id));
  }, [jobQuery.data, navigate]);

  function resetGenerateForm() {
    setTopic("");
    setKeywordsInput("");
    setNotes("");
    setProvider("anthropic");
    setJobId(undefined);
    setSubmitError(null);
  }

  function closeGenerate() {
    setGenerateOpen(false);
    resetGenerateForm();
  }

  function submitGenerate(e?: FormEvent) {
    e?.preventDefault();
    setSubmitError(null);
    const trimmed = topic.trim();
    if (!trimmed) {
      setSubmitError("Topic is required.");
      return;
    }
    requestDraft.mutate(
      {
        topic: trimmed,
        keywords: parseTagsInput(keywordsInput),
        notes: notes.trim() || null,
        provider,
      },
      {
        onSuccess: (job) => setJobId(job.id),
        onError: (err) => setSubmitError(err),
      },
    );
  }

  const job = jobQuery.data;
  const writing = Boolean(jobId) && job?.status !== "failed";
  const failed = job?.status === "failed";

  return (
    <div data-testid="admin-blog-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
            Blog
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-[var(--slate)]/75">
            Articles on the public blog. Drafts are only visible here; published posts appear at
            /blog immediately.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            data-testid="admin-blog-generate-button"
            onClick={() => {
              resetGenerateForm();
              setGenerateOpen(true);
            }}
            className="rounded border border-[var(--mist)] bg-white px-4 py-2 text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--paper)]"
          >
            Generate with AI
          </button>
          <Link
            to={ROUTES.admin.newBlogPost}
            data-testid="admin-blog-new-button"
            className="rounded bg-[var(--ink)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--ink-soft)]"
          >
            New post
          </Link>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <label className="text-sm text-[var(--slate)]">
          Status{" "}
          <select
            data-testid="admin-blog-status-select"
            className="ml-1 rounded border border-[var(--mist)] bg-white px-2 py-1"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as PostStatus | "");
              setPage(1);
            }}
          >
            <option value="">all</option>
            {POST_STATUS_VALUES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--mist)]/50 text-left text-xs uppercase tracking-wide text-[var(--slate)]/70">
              <th className="px-4 py-2.5 font-medium">Title</th>
              <th className="px-4 py-2.5 font-medium">Slug</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Published</th>
              <th className="px-4 py-2.5 text-right font-medium">Views</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--slate)]/60">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && data?.items.length === 0 && (
              <tr data-testid="admin-blog-empty-row">
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--slate)]/60">
                  No posts{status ? ` with status "${status}"` : " yet"}. Write the first one.
                </td>
              </tr>
            )}
            {data?.items.map((post) => (
              <tr
                key={post.id}
                data-testid="admin-blog-row"
                onClick={() => navigate(ROUTES.admin.blogPost(post.id))}
                className="h-10 cursor-pointer border-t border-[var(--mist)] transition-colors hover:bg-[var(--paper)]"
              >
                <td className="max-w-[16rem] truncate px-4 py-2 font-medium text-[var(--ink)]">
                  {post.title}
                </td>
                <td className="max-w-[12rem] truncate px-4 py-2 font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)]">
                  {post.slug}
                </td>
                <td className="px-4 py-2">
                  <Stamp className={statusTones[post.status]}>{post.status}</Stamp>
                </td>
                <td className="px-4 py-2 font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)] tabular-nums">
                  {formatPostDate(post.published_at)}
                </td>
                <td className="px-4 py-2 text-right font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)] tabular-nums">
                  {post.view_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={data} onPageChange={setPage} />}
      </div>

      <Modal
        open={generateOpen}
        onClose={closeGenerate}
        title="Generate with AI"
        data-testid="admin-blog-generate-modal"
        footer={
          writing || failed ? undefined : (
            <>
              <Button type="button" variant="secondary" onClick={closeGenerate}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => submitGenerate()}
                disabled={requestDraft.isPending}
              >
                Generate
              </Button>
            </>
          )
        }
      >
        {writing ? (
          <div className="flex flex-col items-center gap-3 py-4">
            <Spinner />
            <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--slate)]">
              Writing draft… {job?.status ?? "pending"}
            </p>
          </div>
        ) : failed ? (
          <div className="space-y-3">
            <Alert tone="error">{job?.error || "Draft generation failed."}</Alert>
            <Button type="button" onClick={() => submitGenerate()}>
              Retry
            </Button>
          </div>
        ) : (
          <form className="space-y-3" onSubmit={submitGenerate}>
            {!!submitError && <ErrorAlert error={submitError} />}
            <div>
              <label className="mb-1 block text-sm text-[var(--slate)]">Topic</label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                required
                maxLength={200}
                placeholder="What should the post cover?"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-[var(--slate)]">Keywords</label>
              <Input
                value={keywordsInput}
                onChange={(e) => setKeywordsInput(e.target.value)}
                placeholder="comma-separated"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-[var(--slate)]">Notes</label>
              <textarea
                className={TEXTAREA_CLASS}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={500}
                rows={3}
                placeholder="Optional guidance for the model"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-[var(--slate)]">Provider</label>
              <select
                className="w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm"
                value={provider}
                onChange={(e) => setProvider(e.target.value as LlmProvider)}
              >
                <option value="anthropic">anthropic</option>
                <option value="openai">openai</option>
                <option value="gemini">gemini</option>
              </select>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
