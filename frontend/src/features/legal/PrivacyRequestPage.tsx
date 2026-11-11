import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../shared/lib/routes";
import { ApiError } from "../../shared/api";
import { ErrorAlert } from "../../shared/ui";
import { PRIVACY_REQUEST_NOTES_MAX_LENGTH } from "../../shared/lib/policy";
import { submitPrivacyRequest, type PrivacyRequestType } from "../admin";

const TYPES: { value: PrivacyRequestType; label: string; blurb: string }[] = [
  {
    value: "access",
    label: "Access",
    blurb: "Ask what personal data we hold about you (subject to identity verification).",
  },
  {
    value: "delete",
    label: "Delete",
    blurb: "Request deletion of your personal data.",
  },
  {
    value: "suppress",
    label: "Suppress",
    blurb: "Ask us to stop processing your personal data without deleting your request record.",
  },
];

export default function PrivacyRequestPage() {
  const [requestType, setRequestType] = useState<PrivacyRequestType>("suppress");
  const [requesterEmail, setRequesterEmail] = useState("");
  const [requesterName, setRequesterName] = useState("");
  const [subjectEmail, setSubjectEmail] = useState("");
  const [subjectPhone, setSubjectPhone] = useState("");
  const [subjectConsumerKey, setSubjectConsumerKey] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [doneId, setDoneId] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitPrivacyRequest({
        request_type: requestType,
        requester_email: requesterEmail,
        requester_name: requesterName || undefined,
        subject_email: subjectEmail || undefined,
        subject_phone: subjectPhone || undefined,
        subject_consumer_key: subjectConsumerKey || undefined,
        notes: notes || undefined,
      });
      setDoneId(res.id);
    } catch (err) {
      setError(err instanceof ApiError ? err : "Something went wrong submitting your request.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--paper)]" data-testid="privacy-request-page">
      <div className="mx-auto max-w-xl px-6 py-12">
        <p className="text-sm text-[var(--slate)]/70">
          <Link
            to={ROUTES.legal.privacy}
            className="text-[var(--teal-deep)] hover:underline"
            data-testid="privacy-request-privacy-link"
          >
            ← Privacy Policy
          </Link>
        </p>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl font-semibold text-[var(--ink)]">
          Privacy request
        </h1>
        <p className="mt-2 text-sm text-[var(--slate)]/80">
          Submit an access, delete, or suppress request for your personal data. We may contact you
          to verify identity before fulfilling it.
        </p>

        {doneId ? (
          <div
            className="mt-8 rounded border border-[var(--line)] bg-[var(--paper)] p-6"
            data-testid="privacy-request-success"
          >
            <p className="font-medium text-[var(--ink)]">Request received</p>
            <p className="mt-2 text-sm text-[var(--slate)]">
              Reference{" "}
              <code className="text-xs" data-testid="privacy-request-reference">
                {doneId}
              </code>
              . Keep this if you contact support.
            </p>
            <Link
              to={ROUTES.home}
              className="mt-4 inline-block text-sm text-[var(--teal-deep)] hover:underline"
              data-testid="privacy-request-home-link"
            >
              Back to home
            </Link>
          </div>
        ) : (
          <form
            onSubmit={onSubmit}
            className="mt-8 space-y-5 rounded border border-[var(--line)] bg-[var(--paper)] p-6"
            data-testid="privacy-request-form"
          >
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-[var(--ink)]">Request type</legend>
              {TYPES.map((t) => (
                <label
                  key={t.value}
                  className="flex cursor-pointer gap-3 rounded border border-[var(--line)] p-3"
                >
                  <input
                    type="radio"
                    name="request_type"
                    value={t.value}
                    checked={requestType === t.value}
                    onChange={() => setRequestType(t.value)}
                    className="mt-1"
                    data-testid="privacy-request-type-radio"
                    data-id={t.value}
                  />
                  <span>
                    <span className="font-medium text-[var(--ink)]">{t.label}</span>
                    <span className="mt-0.5 block text-xs text-[var(--slate)]/75">{t.blurb}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            <label className="block text-sm">
              <span className="font-medium text-[var(--ink)]">Your email</span>
              <input
                required
                type="email"
                className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2"
                value={requesterEmail}
                onChange={(e) => setRequesterEmail(e.target.value)}
                data-testid="privacy-request-requester-email-input"
              />
            </label>

            <label className="block text-sm">
              <span className="font-medium text-[var(--ink)]">Your name (optional)</span>
              <input
                className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2"
                value={requesterName}
                onChange={(e) => setRequesterName(e.target.value)}
                data-testid="privacy-request-requester-name-input"
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="font-medium text-[var(--ink)]">Subject email</span>
                <input
                  type="email"
                  className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2"
                  value={subjectEmail}
                  onChange={(e) => setSubjectEmail(e.target.value)}
                  placeholder="Defaults to your email"
                  data-testid="privacy-request-subject-email-input"
                />
              </label>
              <label className="block text-sm">
                <span className="font-medium text-[var(--ink)]">Subject phone</span>
                <input
                  className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2"
                  value={subjectPhone}
                  onChange={(e) => setSubjectPhone(e.target.value)}
                  data-testid="privacy-request-subject-phone-input"
                />
              </label>
            </div>

            <label className="block text-sm">
              <span className="font-medium text-[var(--ink)]">
                Account / reference id (if known)
              </span>
              <input
                className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2"
                value={subjectConsumerKey}
                onChange={(e) => setSubjectConsumerKey(e.target.value)}
                data-testid="privacy-request-consumer-key-input"
              />
            </label>

            <label className="block text-sm">
              <span className="font-medium text-[var(--ink)]">Notes</span>
              <textarea
                className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2"
                rows={3}
                maxLength={PRIVACY_REQUEST_NOTES_MAX_LENGTH}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                data-testid="privacy-request-notes-input"
              />
            </label>

            <ErrorAlert error={error} data-testid="privacy-request-error" />

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-[var(--ink)] px-4 py-2.5 font-medium text-white disabled:opacity-50"
              data-testid="privacy-request-submit"
            >
              {submitting ? "Submitting…" : "Submit request"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
