"""API key auth: Bearer sk_live_… unlocks member-scoped org endpoints."""

from tests.helpers import create_org, register_and_login


async def test_api_key_can_read_wallet(client):
    _, headers = await register_and_login(client, "apikey-owner@example.com")
    org = await create_org(client, headers, name="Key Co")
    org_id = org["id"]

    create = await client.post(
        f"/api/orgs/{org_id}/api-keys",
        json={"name": "CI"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    raw_key = create.json()["raw_key"]
    assert raw_key.startswith("sk_live_")

    key_headers = {"Authorization": f"Bearer {raw_key}"}
    res = await client.get(f"/api/orgs/{org_id}/credits", headers=key_headers)
    assert res.status_code == 200, res.text
    assert "balance" in res.json()


async def test_api_key_rejected_for_admin_endpoint(client):
    _, headers = await register_and_login(client, "apikey-admin@example.com")
    org = await create_org(client, headers, name="Admin Gate")
    org_id = org["id"]

    create = await client.post(
        f"/api/orgs/{org_id}/api-keys",
        json={"name": "CI"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    raw_key = create.json()["raw_key"]

    # Creating another key requires Admin — API keys are member-capped.
    res = await client.post(
        f"/api/orgs/{org_id}/api-keys",
        json={"name": "Nope"},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert res.status_code == 403, res.text


async def test_api_key_wrong_org_is_404(client):
    _, headers_a = await register_and_login(client, "apikey-a@apikey-org-a.com")
    org_a = await create_org(client, headers_a, name="Org A")
    create = await client.post(
        f"/api/orgs/{org_a['id']}/api-keys",
        json={"name": "A"},
        headers=headers_a,
    )
    raw_key = create.json()["raw_key"]

    _, headers_b = await register_and_login(client, "apikey-b@apikey-org-b.com")
    org_b = await create_org(client, headers_b, name="Org B")

    res = await client.get(
        f"/api/orgs/{org_b['id']}/credits",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert res.status_code == 404, res.text


async def test_revoked_api_key_is_401(client):
    _, headers = await register_and_login(client, "apikey-revoke@example.com")
    org = await create_org(client, headers, name="Revoke Co")
    org_id = org["id"]

    create = await client.post(
        f"/api/orgs/{org_id}/api-keys",
        json={"name": "Temp"},
        headers=headers,
    )
    body = create.json()
    raw_key = body["raw_key"]
    key_id = body["id"]

    revoke = await client.delete(f"/api/orgs/{org_id}/api-keys/{key_id}", headers=headers)
    assert revoke.status_code == 204, revoke.text

    res = await client.get(
        f"/api/orgs/{org_id}/credits",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert res.status_code == 401, res.text
