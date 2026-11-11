async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_unknown_route_renders_problem_json(client):
    res = await client.get("/api/nope")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["code"] == "ERR_REQ_002"
    assert "instance" in body  # correlation id for support lookups
    assert res.headers["x-request-id"]
