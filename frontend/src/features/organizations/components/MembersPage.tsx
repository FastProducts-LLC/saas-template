import { useEntitlements, formatLimit } from "../../entitlements";
import { useAuth } from "../../auth";
import { Counter, CounterStrip, PageHeader, SectionRule } from "../../../shared/ui";
import { useInvitations, useMembers } from "../api/hooks";
import { useOrg } from "../model/current-org";
import { isAdmin } from "../model/permissions";
import InvitationsTable from "./InvitationsTable";
import InviteForm from "./InviteForm";
import MembersTable from "./MembersTable";

export default function MembersPage() {
  const { user } = useAuth();
  const { currentOrg } = useOrg();
  const orgId = currentOrg!.id;
  const actorRole = currentOrg!.role;
  const admin = isAdmin(actorRole);

  const { data: members = [] } = useMembers(orgId);
  const { data: invitations = [] } = useInvitations(orgId, admin);

  const { data: entitlements } = useEntitlements(orgId);
  const seats = entitlements?.entitlements.find((item) => item.key === "seats");
  const pendingCount = invitations.length;

  return (
    <div data-testid="members-page" className="max-w-[1200px]">
      <div className="gd-stagger-item" style={{ "--i": 0 } as React.CSSProperties}>
        <PageHeader
          title="Members"
          description={`People who can use ${currentOrg!.name}. Owners and admins manage billing, keys, and invitations.`}
        />
      </div>

      <div className="gd-stagger-item mt-8" style={{ "--i": 1 } as React.CSSProperties}>
        <CounterStrip>
          <Counter testId="members-active-count" value={members.length} label="Active members" />
          {admin && (
            <Counter
              testId="members-pending-count"
              value={pendingCount}
              label="Pending invitations"
            />
          )}
          {seats && (
            <Counter
              testId="members-seats"
              value={
                <>
                  {seats.used}
                  <span className="text-[var(--slate)]/60"> / {formatLimit(seats.limit)}</span>
                </>
              }
              label="Seats used"
            />
          )}
        </CounterStrip>
      </div>

      <div
        className={`mt-10 grid gap-8 ${admin ? "lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" : ""}`}
      >
        <div className="gd-stagger-item min-w-0" style={{ "--i": 2 } as React.CSSProperties}>
          <SectionRule index="01" title="People" />
          <MembersTable
            orgId={orgId}
            members={members}
            currentUserId={user?.id}
            actorRole={actorRole}
          />

          {admin && invitations.length > 0 && (
            <div className="mt-10">
              <SectionRule index="02" title="Pending invitations" />
              <InvitationsTable orgId={orgId} invitations={invitations} />
            </div>
          )}
        </div>

        {admin && (
          <aside className="gd-stagger-item" style={{ "--i": 3 } as React.CSSProperties}>
            <InviteForm orgId={orgId} />
          </aside>
        )}
      </div>
    </div>
  );
}
