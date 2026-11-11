import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { ApiError } from "../../../shared/api";
import {
  COMMUNITY_BIO_MAX_LENGTH,
  COMMUNITY_DISPLAY_NAME_MAX_LENGTH,
  COMMUNITY_HANDLE_MAX_LENGTH,
} from "../../../shared/lib/policy";
import {
  Alert,
  Avatar,
  Button,
  Input,
  Spinner,
  Stamp,
  Textarea,
  ErrorAlert,
} from "../../../shared/ui";
import { useDirectory, useJoinCommunity, useMyCommunity } from "../api/hooks";
import ProfileEditor from "./ProfileEditor";
import type { Member } from "../model/types";

function JoinForm() {
  const join = useJoinCommunity();
  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    join.mutate(
      { handle, display_name: displayName, bio: bio || null },
      {
        onError: (err: unknown) => {
          if (err instanceof ApiError && Object.keys(err.fields).length > 0) {
            setFieldErrors(err.fields);
          } else if (err instanceof ApiError && err.code === "ERR_COMM_002") {
            setFieldErrors({ handle: err.userMessage });
          } else {
            setError(err);
          }
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-md" data-testid="community-join">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--ink)]">
        Join the community
      </h1>
      <p className="mt-2 text-sm text-[var(--slate)]">
        Create your member profile to browse the directory. Messaging is part of the premium
        membership.
      </p>
      {!!error && <ErrorAlert error={error} data-testid="community-join-error" />}
      <form onSubmit={submit} className="mt-6 space-y-4">
        <Input
          label="Handle"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          placeholder="jane_doe"
          maxLength={COMMUNITY_HANDLE_MAX_LENGTH}
          pattern="[A-Za-z0-9_]{3,30}"
          title="3-30 characters: letters, numbers, underscores"
          required
          error={fieldErrors.handle}
          data-testid="community-join-handle"
        />
        <Input
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          maxLength={COMMUNITY_DISPLAY_NAME_MAX_LENGTH}
          required
          error={fieldErrors.display_name}
          data-testid="community-join-display-name"
        />
        <Textarea
          label="Bio (optional)"
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          maxLength={COMMUNITY_BIO_MAX_LENGTH}
          rows={3}
          error={fieldErrors.bio}
        />
        <p className="text-xs text-[var(--slate)]/65">
          Your handle, display name, and bio are visible to all signed-in community members.
        </p>
        <Button type="submit" loading={join.isPending} data-testid="community-join-submit">
          Create profile
        </Button>
      </form>
    </div>
  );
}

function MemberCard({ member }: { member: Member }) {
  return (
    <Link
      to={ROUTES.community.member(member.handle)}
      data-testid="community-member-card"
      data-handle={member.handle}
      className="flex items-start gap-3 border border-[var(--line)] bg-white p-4 transition-colors hover:border-[var(--teal)]"
      style={{ borderRadius: 4 }}
    >
      <Avatar name={member.display_name} src={member.avatar_url} size="lg" />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-[var(--ink)]">{member.display_name}</p>
        <p className="truncate font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)]/75">
          @{member.handle}
        </p>
        {member.tier === "premium" && (
          <Stamp className="mt-1.5 border-[var(--teal-deep)] text-[var(--teal-deep)]">
            Premium
          </Stamp>
        )}
        {member.bio && (
          <p className="mt-1.5 line-clamp-2 text-[13px] text-[var(--slate)]">{member.bio}</p>
        )}
      </div>
    </Link>
  );
}

function Directory() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useDirectory(search, page);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div data-testid="community-directory">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--ink)]">
            Community
          </h1>
          <p className="mt-1 text-sm text-[var(--slate)]">
            {data ? `${data.total.toLocaleString()} members` : " "}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search members…"
            data-testid="community-directory-search"
          />
          <Link
            to={ROUTES.community.messages}
            className="whitespace-nowrap text-sm font-medium text-[var(--teal-deep)] hover:underline"
            data-testid="community-messages-link"
          >
            Messages
          </Link>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data?.items.map((member) => (
              <MemberCard key={member.handle} member={member} />
            ))}
          </div>
          {data?.items.length === 0 && (
            <p
              data-testid="community-directory-empty"
              className="mt-10 text-center text-sm text-[var(--slate)]/60"
            >
              No members match that search.
            </p>
          )}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-between text-sm text-[var(--slate)]">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="font-medium text-[var(--teal-deep)] hover:underline disabled:text-[var(--slate)]/40 disabled:no-underline"
              >
                ← Previous
              </button>
              <span className="font-[family-name:var(--font-mono)] tabular-nums">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="font-medium text-[var(--teal-deep)] hover:underline disabled:text-[var(--slate)]/40 disabled:no-underline"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function CommunityPage() {
  const [searchParams] = useSearchParams();
  const checkoutReturned = searchParams.get("status") === "success";
  const { data, isLoading } = useMyCommunity({ pollUntilPremium: checkoutReturned });

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="gd-page-in">
      {checkoutReturned && (
        <div className="mb-6">
          {data?.membership?.is_premium ? (
            <Alert tone="success" data-testid="community-upgrade-success">
              You're a premium member — messaging is unlocked.
            </Alert>
          ) : (
            <Alert tone="info" data-testid="community-upgrade-pending">
              Payment received — activating your membership…
            </Alert>
          )}
        </div>
      )}
      {data?.profile ? (
        <>
          <ProfileEditor profile={data.profile} />
          <Directory />
        </>
      ) : (
        <JoinForm />
      )}
    </div>
  );
}
