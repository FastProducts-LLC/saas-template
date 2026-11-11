import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { isApiErrorWithCode } from "../../../shared/api";
import { Avatar, Button, Modal, Spinner, Stamp, ErrorAlert } from "../../../shared/ui";
import { useMember, useMyCommunity, useStartConversation } from "../api/hooks";

export default function MemberProfilePage() {
  const { handle } = useParams<{ handle: string }>();
  const navigate = useNavigate();
  const { data: member, isLoading, isError, error: memberError } = useMember(handle);
  const { data: me } = useMyCommunity();
  const start = useStartConversation();
  const [showUpgradePrompt, setShowUpgradePrompt] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const isSelf = me?.profile?.handle === handle;

  const message = () => {
    if (!me?.membership?.is_premium) {
      setShowUpgradePrompt(true);
      return;
    }
    start.mutate(handle!, {
      onSuccess: (conversation) => navigate(ROUTES.community.conversation(conversation.id)),
      onError: (err: unknown) => {
        // Belt-and-braces: the server re-checks premium on every send path.
        if (isApiErrorWithCode(err, "ERR_COMM_004")) {
          setShowUpgradePrompt(true);
        } else {
          setError(err);
        }
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  if (isError || !member) {
    return (
      <div className="gd-page-in mx-auto max-w-lg" data-testid="community-member-missing">
        <ErrorAlert error={memberError} />
        <Link
          to={ROUTES.community.list}
          className="mt-4 inline-block text-sm font-medium text-[var(--teal-deep)] hover:underline"
        >
          ← Back to the directory
        </Link>
      </div>
    );
  }

  return (
    <div className="gd-page-in mx-auto max-w-lg" data-testid="community-member-page">
      <Link
        to={ROUTES.community.list}
        className="text-sm font-medium text-[var(--teal-deep)] hover:underline"
      >
        ← Directory
      </Link>

      <div className="mt-4 border border-[var(--line)] bg-white p-6" style={{ borderRadius: 4 }}>
        <div className="flex items-start gap-4">
          <Avatar name={member.display_name} src={member.avatar_url} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--ink)]">
              {member.display_name}
            </h1>
            <p className="font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)]/75">
              @{member.handle}
            </p>
            <div className="mt-2 flex items-center gap-2">
              {member.tier === "premium" && (
                <Stamp className="border-[var(--teal-deep)] text-[var(--teal-deep)]">Premium</Stamp>
              )}
              <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]/60">
                joined {new Date(member.joined_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>

        {member.bio && (
          <p className="mt-4 border-t border-[var(--line)] pt-4 text-sm text-[var(--slate)]">
            {member.bio}
          </p>
        )}

        {!isSelf && (
          <div className="mt-5 border-t border-[var(--line)] pt-4">
            <Button
              onClick={message}
              loading={start.isPending}
              data-testid="community-member-message-button"
            >
              Message
            </Button>
          </div>
        )}
      </div>

      {!!error && (
        <div className="mt-4">
          <ErrorAlert error={error} />
        </div>
      )}

      <Modal
        open={showUpgradePrompt}
        onClose={() => setShowUpgradePrompt(false)}
        title="Messaging is a premium feature"
      >
        <p className="text-sm text-[var(--slate)]">
          Direct messages are part of the premium membership. Upgrade to start a conversation with{" "}
          {member.display_name}.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setShowUpgradePrompt(false)}>
            Not now
          </Button>
          <Button
            onClick={() => navigate(ROUTES.community.upgrade)}
            data-testid="community-upgrade-cta"
          >
            See plans
          </Button>
        </div>
      </Modal>
    </div>
  );
}
