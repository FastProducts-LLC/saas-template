"""Organizations API tests: org lifecycle, members, roles, and invitations."""

import pytest_asyncio

from app.core.config import settings
from app.domains.auth.infrastructure.security import JwtTokenService
from app.domains.organizations.application import use_cases as uc
from app.domains.organizations.infrastructure.repositories import SqlAlchemyOrgRepository
from app.domains.organizations.interface.deps import get_db, get_invite_member
from app.main import app
from tests.helpers import create_org, register_and_login

# ── Invitation token capture ─────────────────────────────────────────
#
# InviteMember hands the RAW (unhashed) invitation token to its notifier; only
# the hash is persisted. To accept an invitation in a test we must observe that
# raw token. We override the `get_invite_member` use-case factory with one that
# swaps in a recording notifier, so the real use case (and real DB session)
# still runs — we only intercept the side-channel the email would have used.


class _RecordingNotifier:
    """Stands in for EmailInvitationNotifier; records the raw token."""

    def __init__(self) -> None:
        self.tokens: list[str] = []

    async def send_invitation(self, invitation, org, inviter, raw_token: str) -> None:
        self.tokens.append(raw_token)


@pytest_asyncio.fixture
async def invite_recorder():
    """Override get_invite_member to capture raw invitation tokens.

    Cleans up the override afterwards so other suites are unaffected.
    """
    recorder = _RecordingNotifier()

    def _factory(db=None):
        # Resolve the same request-scoped session FastAPI would inject.
        return uc.InviteMember(
            SqlAlchemyOrgRepository(db),
            JwtTokenService(),
            recorder,
            settings.invitation_ttl_days,
        )

    from fastapi import Depends

    async def _override(db=Depends(get_db)):
        return _factory(db)

    app.dependency_overrides[get_invite_member] = _override
    try:
        yield recorder
    finally:
        app.dependency_overrides.pop(get_invite_member, None)


async def _invite(client, headers, org_id, email, role="member"):
    return await client.post(
        f"/api/orgs/{org_id}/invitations",
        json={"email": email, "role": role},
        headers=headers,
    )


# ── Create / list / get ──────────────────────────────────────────────


async def test_create_org_makes_caller_owner(client):
    _, headers = await register_and_login(client)
    body = await create_org(client, headers, "Acme Inc")
    assert body["name"] == "Acme Inc"
    assert body["role"] == "owner"
    assert body["slug"] == "acme-inc"


async def test_two_orgs_same_name_get_distinct_slugs(client):
    _, headers_a = await register_and_login(client, "slug-a@slug-test-a.com")
    _, headers_b = await register_and_login(client, "slug-b@slug-test-b.com")
    first = await create_org(client, headers_a, "Acme")
    second = await create_org(client, headers_b, "Acme")
    assert first["slug"] == "acme"
    assert second["slug"] != first["slug"]
    assert second["slug"].startswith("acme-")


async def test_create_org_requires_auth(client):
    res = await client.post("/api/orgs", json={"name": "Acme"})
    assert res.status_code == 401


async def test_list_my_orgs_returns_only_own(client):
    _, alice = await register_and_login(client, "alice@alice-co.com")
    _, bob = await register_and_login(client, "bob@bob-co.com")
    await create_org(client, alice, "Alice Co")
    await create_org(client, bob, "Bob Co")

    res = await client.get("/api/orgs", headers=alice)
    assert res.status_code == 200
    names = {o["name"] for o in res.json()}
    assert names == {"Alice Co"}


async def test_get_org_returns_role(client):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    res = await client.get(f"/api/orgs/{org['id']}", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == org["id"]
    assert body["role"] == "owner"


async def test_non_member_gets_404_not_403(client):
    _, owner = await register_and_login(client, "owner@example.com")
    _, outsider = await register_and_login(client, "outsider@example.com")
    org = await create_org(client, owner)

    res = await client.get(f"/api/orgs/{org['id']}", headers=outsider)
    # Existence must never leak: a non-member sees a 404, not a 403.
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_PERM_002"


# ── Rename / delete ──────────────────────────────────────────────────


async def test_rename_as_admin_works(client, db, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    user, admin = await register_and_login(client, "admin@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "admin@example.com", role="admin")
    token = invite_recorder.tokens[-1]
    accept = await client.post("/api/invitations/accept", json={"token": token}, headers=admin)
    assert accept.status_code == 200

    res = await client.patch(f"/api/orgs/{org['id']}", json={"name": "Renamed"}, headers=admin)
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed"


async def test_member_cannot_rename(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, member = await register_and_login(client, "member@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "member@example.com")
    token = invite_recorder.tokens[-1]
    await client.post("/api/invitations/accept", json={"token": token}, headers=member)

    res = await client.patch(f"/api/orgs/{org['id']}", json={"name": "Nope"}, headers=member)
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_PERM_001"


async def test_delete_as_owner_removes_org(client):
    _, owner = await register_and_login(client)
    org = await create_org(client, owner)

    res = await client.delete(f"/api/orgs/{org['id']}", headers=owner)
    assert res.status_code == 204

    gone = await client.get(f"/api/orgs/{org['id']}", headers=owner)
    assert gone.status_code == 404


async def test_admin_cannot_delete_org(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, admin = await register_and_login(client, "admin@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "admin@example.com", role="admin")
    token = invite_recorder.tokens[-1]
    await client.post("/api/invitations/accept", json={"token": token}, headers=admin)

    res = await client.delete(f"/api/orgs/{org['id']}", headers=admin)
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_PERM_001"


# ── Members ──────────────────────────────────────────────────────────


async def test_list_members_includes_owner(client):
    user, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)

    res = await client.get(f"/api/orgs/{org['id']}/members", headers=owner)
    assert res.status_code == 200
    members = res.json()
    assert len(members) == 1
    assert members[0]["email"] == "owner@example.com"
    assert members[0]["role"] == "owner"


async def test_promote_member_to_admin(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, member = await register_and_login(client, "member@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "member@example.com")
    token = invite_recorder.tokens[-1]
    await client.post("/api/invitations/accept", json={"token": token}, headers=member)

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    target = next(m for m in members if m["email"] == "member@example.com")

    res = await client.patch(
        f"/api/orgs/{org['id']}/members/{target['id']}",
        json={"role": "admin"},
        headers=owner,
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


async def test_remove_member_as_admin(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, member = await register_and_login(client, "member@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "member@example.com")
    token = invite_recorder.tokens[-1]
    await client.post("/api/invitations/accept", json={"token": token}, headers=member)

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    target = next(m for m in members if m["email"] == "member@example.com")

    res = await client.delete(f"/api/orgs/{org['id']}/members/{target['id']}", headers=owner)
    assert res.status_code == 204

    # The removed member no longer sees the org at all.
    assert (await client.get(f"/api/orgs/{org['id']}", headers=member)).status_code == 404


async def test_member_can_remove_self(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, member = await register_and_login(client, "member@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "member@example.com")
    token = invite_recorder.tokens[-1]
    await client.post("/api/invitations/accept", json={"token": token}, headers=member)

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    me = next(m for m in members if m["email"] == "member@example.com")

    res = await client.delete(f"/api/orgs/{org['id']}/members/{me['id']}", headers=member)
    assert res.status_code == 204
    assert (await client.get(f"/api/orgs/{org['id']}", headers=member)).status_code == 404


async def test_member_cannot_remove_another_member(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, m1 = await register_and_login(client, "m1@example.com")
    _, m2 = await register_and_login(client, "m2@example.com")
    org = await create_org(client, owner)

    for email, hdr in (("m1@example.com", m1), ("m2@example.com", m2)):
        await _invite(client, owner, org["id"], email)
        await client.post(
            "/api/invitations/accept",
            json={"token": invite_recorder.tokens[-1]},
            headers=hdr,
        )

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    victim = next(m for m in members if m["email"] == "m2@example.com")

    res = await client.delete(f"/api/orgs/{org['id']}/members/{victim['id']}", headers=m1)
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_PERM_001"


async def test_cannot_remove_last_owner(client):
    user, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    me = members[0]

    res = await client.delete(f"/api/orgs/{org['id']}/members/{me['id']}", headers=owner)
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_ORG_001"


async def test_cannot_demote_last_owner(client):
    _, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    me = members[0]

    res = await client.patch(
        f"/api/orgs/{org['id']}/members/{me['id']}",
        json={"role": "admin"},
        headers=owner,
    )
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_ORG_001"


async def test_non_owner_cannot_grant_owner_role(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, admin = await register_and_login(client, "admin@example.com")
    _, member = await register_and_login(client, "member@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "admin@example.com", role="admin")
    await client.post(
        "/api/invitations/accept",
        json={"token": invite_recorder.tokens[-1]},
        headers=admin,
    )
    await _invite(client, owner, org["id"], "member@example.com")
    await client.post(
        "/api/invitations/accept",
        json={"token": invite_recorder.tokens[-1]},
        headers=member,
    )

    members = (await client.get(f"/api/orgs/{org['id']}/members", headers=owner)).json()
    target = next(m for m in members if m["email"] == "member@example.com")

    # An admin may pass the require_role(ADMIN) gate but cannot grant owner.
    res = await client.patch(
        f"/api/orgs/{org['id']}/members/{target['id']}",
        json={"role": "owner"},
        headers=admin,
    )
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_PERM_001"


# ── Invitations ──────────────────────────────────────────────────────


async def test_invite_member_creates_pending_invitation(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)

    res = await _invite(client, owner, org["id"], "invitee@example.com")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "invitee@example.com"
    assert body["role"] == "member"
    # The raw token went to the notifier, never the response.
    assert invite_recorder.tokens


async def test_list_pending_invitations(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)
    await _invite(client, owner, org["id"], "a@example.com")
    await _invite(client, owner, org["id"], "b@example.com")

    res = await client.get(f"/api/orgs/{org['id']}/invitations", headers=owner)
    assert res.status_code == 200
    emails = {i["email"] for i in res.json()}
    assert emails == {"a@example.com", "b@example.com"}


async def test_revoke_invitation(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)
    inv = (await _invite(client, owner, org["id"], "gone@example.com")).json()

    res = await client.delete(f"/api/orgs/{org['id']}/invitations/{inv['id']}", headers=owner)
    assert res.status_code == 204

    listed = await client.get(f"/api/orgs/{org['id']}/invitations", headers=owner)
    assert listed.json() == []


async def test_accept_invitation_adds_membership(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, invitee = await register_and_login(client, "invitee@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "invitee@example.com")
    token = invite_recorder.tokens[-1]

    res = await client.post("/api/invitations/accept", json={"token": token}, headers=invitee)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == org["id"]
    assert body["role"] == "member"

    # Membership is now real: the invitee can read the org.
    assert (await client.get(f"/api/orgs/{org['id']}", headers=invitee)).status_code == 200


async def test_invite_existing_member_rejected(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)

    res = await _invite(client, owner, org["id"], "owner@example.com")
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_ORG_002"


async def test_duplicate_pending_invite_rejected(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    org = await create_org(client, owner)

    first = await _invite(client, owner, org["id"], "dup@example.com")
    assert first.status_code == 201
    second = await _invite(client, owner, org["id"], "dup@example.com")
    assert second.status_code == 409
    assert second.json()["code"] == "ERR_ORG_002"


async def test_accept_invalid_token(client):
    _, invitee = await register_and_login(client, "invitee@example.com")
    res = await client.post(
        "/api/invitations/accept", json={"token": "not-a-real-token"}, headers=invitee
    )
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_PERM_003"


async def test_accept_with_wrong_email_account(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, wrong = await register_and_login(client, "wrong@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "invitee@example.com")
    token = invite_recorder.tokens[-1]

    # The signed-in account's email doesn't match the invitation's address.
    res = await client.post("/api/invitations/accept", json={"token": token}, headers=wrong)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_PERM_003"


async def test_accept_when_already_member(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@example.com")
    _, invitee = await register_and_login(client, "invitee@example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "invitee@example.com")
    token = invite_recorder.tokens[-1]
    first = await client.post("/api/invitations/accept", json={"token": token}, headers=invitee)
    assert first.status_code == 200

    # Replaying the same token after joining is rejected. Acceptance consumed
    # the invitation, so the token now resolves to a non-pending invitation
    # and surfaces as InvitationInvalid (ERR_PERM_003).
    replay = await client.post("/api/invitations/accept", json={"token": token}, headers=invitee)
    assert replay.status_code == 404
    assert replay.json()["code"] == "ERR_PERM_003"


# ── Company domain capture ───────────────────────────────────────────


async def _claim_domain(client, headers, org_id, domain):
    return await client.put(f"/api/orgs/{org_id}/domain", json={"domain": domain}, headers=headers)


async def test_owner_claims_own_email_domain(client):
    _, owner = await register_and_login(client, "founder@intel-example.com")
    org = await create_org(client, owner, name="Intel")

    res = await _claim_domain(client, owner, org["id"], "Intel-Example.COM")
    assert res.status_code == 200, res.text
    assert res.json()["email_domain"] == "intel-example.com"


async def test_claim_rejects_public_email_provider(client):
    # The domain being claimed is rejected purely for being a shared
    # provider (normalize_claimable_domain checks PUBLIC_EMAIL_DOMAINS before
    # the owner-email match), so the owner's own email doesn't need to be on
    # that provider.
    _, owner = await register_and_login(client, "founder@claim-check-example.com")
    org = await create_org(client, owner)

    res = await _claim_domain(client, owner, org["id"], "gmail.com")
    assert res.status_code == 400
    assert res.json()["code"] == "ERR_ORG_005"


async def test_claim_rejects_domain_not_matching_owner_email(client):
    _, owner = await register_and_login(client, "founder@acme-example.com")
    org = await create_org(client, owner)

    res = await _claim_domain(client, owner, org["id"], "someone-elses-company.com")
    assert res.status_code == 400
    assert res.json()["code"] == "ERR_ORG_005"


async def test_create_org_blocked_when_domain_already_claimed(client):
    _, first = await register_and_login(client, "a@shared-example.com")
    org = await create_org(client, first, name="First")
    # verified_claim auto-attaches the company domain on create when verified.
    assert org["email_domain"] == "shared-example.com"

    _, second = await register_and_login(client, "b@shared-example.com")
    res = await client.post(
        "/api/orgs",
        json={"name": "Second", "intended_use": "Automated test suite usage"},
        headers=second,
    )
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_ORG_007"


async def test_unverified_user_cannot_create_org(client):
    _, headers = await register_and_login(client, "unverified@gate-example.com", verified=False)
    res = await client.post(
        "/api/orgs",
        json={"name": "Blocked", "intended_use": "Should not create"},
        headers=headers,
    )
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_AUTH_005"


async def test_unverified_org_create_does_not_squat_domain(client, monkeypatch):
    """With the gate off, org create still must not claim an unverified domain."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "email_verification_gate", "none")
    monkeypatch.setattr(settings, "domain_claim_mode", "verified_claim")

    _, headers = await register_and_login(client, "squatter@prey-corp.com", verified=False)
    org = await create_org(client, headers, name="Squat Co")
    assert org["email_domain"] is None

    # A later verified employee can still claim / create without DomainOrgExists.
    _, real = await register_and_login(client, "employee@prey-corp.com")
    claimed = await create_org(client, real, name="Real Co")
    assert claimed["email_domain"] == "prey-corp.com"


async def test_admin_cannot_claim_domain(client, invite_recorder):
    _, owner = await register_and_login(client, "owner@corp-example.com")
    _, admin = await register_and_login(client, "admin@corp-example.com")
    org = await create_org(client, owner)

    await _invite(client, owner, org["id"], "admin@corp-example.com", role="admin")
    await client.post(
        "/api/invitations/accept", json={"token": invite_recorder.tokens[-1]}, headers=admin
    )

    res = await _claim_domain(client, admin, org["id"], "corp-example.com")
    assert res.status_code == 403


async def test_owner_releases_domain(client):
    _, owner = await register_and_login(client, "founder@release-example.com")
    org = await create_org(client, owner)
    await _claim_domain(client, owner, org["id"], "release-example.com")

    res = await client.put(f"/api/orgs/{org['id']}/domain", json={"domain": None}, headers=owner)
    assert res.status_code == 200
    assert res.json()["email_domain"] is None


async def test_verified_email_on_claimed_domain_auto_joins(client):
    from datetime import timedelta

    from app.core.security import create_action_token
    from app.domains.auth.application.use_cases import PURPOSE_VERIFY_EMAIL

    _, owner = await register_and_login(client, "founder@autojoin-example.com")
    org = await create_org(client, owner, name="AutoJoin Inc")
    await _claim_domain(client, owner, org["id"], "autojoin-example.com")

    hire, hire_headers = await register_and_login(
        client, "newhire@autojoin-example.com", verified=False
    )
    # Before verification: no membership — an unverified address proves nothing.
    orgs = await client.get("/api/orgs", headers=hire_headers)
    assert orgs.json() == []

    token = create_action_token(hire["id"], PURPOSE_VERIFY_EMAIL, timedelta(hours=1))
    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 204, res.text

    orgs = (await client.get("/api/orgs", headers=hire_headers)).json()
    assert [o["id"] for o in orgs] == [org["id"]]
    assert orgs[0]["role"] == "member"

    # Clicking the link again must not duplicate the membership.
    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 204
    assert len((await client.get("/api/orgs", headers=hire_headers)).json()) == 1


async def test_verified_email_on_unclaimed_domain_joins_nothing(client):
    from datetime import timedelta

    from app.core.security import create_action_token
    from app.domains.auth.application.use_cases import PURPOSE_VERIFY_EMAIL

    user, headers = await register_and_login(client, "solo@nobody-claimed-this.com")
    token = create_action_token(user["id"], PURPOSE_VERIFY_EMAIL, timedelta(hours=1))
    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 204
    assert (await client.get("/api/orgs", headers=headers)).json() == []


# ── Hardening: membership race + single-line org names ───────────────


async def test_duplicate_membership_insert_is_already_member_not_500(client, db):
    """Race backstop. Parallel accepts of one invitation all pass the
    use-case pre-check; the unique constraint rejects the losers. That must
    surface as AlreadyMember (409), not a raw IntegrityError (500)."""
    import pytest

    from app.domains.organizations.domain import AlreadyMember, Membership, Role

    user, headers = await register_and_login(client)
    org = await create_org(client, headers)
    with pytest.raises(AlreadyMember):
        await SqlAlchemyOrgRepository(db).add_membership(
            Membership(organization_id=org["id"], user_id=user["id"], role=Role.MEMBER)
        )
    await db.rollback()


async def test_org_name_rejects_line_breaks_and_control_chars(client):
    _, headers = await register_and_login(client)
    for bad in ("Acme\r\nBcc: evil@example.com", "Acme\nInc", "Acme\x00", "Acme Inc", " \t "):
        res = await client.post(
            "/api/orgs", json={"name": bad, "intended_use": "testing"}, headers=headers
        )
        assert res.status_code == 422, (bad, res.text)
    org = await create_org(client, headers, "  Acme & Søns 🚀 ")
    assert org["name"] == "Acme & Søns 🚀"
    res = await client.patch(
        f"/api/orgs/{org['id']}", json={"name": "New\r\nName"}, headers=headers
    )
    assert res.status_code == 422, res.text
