// changePassword must persist the fresh token pair the backend returns —
// the server revokes every session, so losing it strands this device.

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  configureApi,
  getAccessToken,
  setAccessToken,
  type RefreshTokenStore,
} from "../../../shared/api/client";
import { changePassword } from "./endpoints";

const fetchMock = vi.fn();

describe("changePassword", () => {
  let stored: string | null;
  const refreshTokens: RefreshTokenStore = {
    get: async () => stored,
    set: async (t) => {
      stored = t;
    },
  };

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    stored = "refresh-old";
    setAccessToken("access-old");
    configureApi({
      baseUrl: "http://test/api",
      refreshTokens,
      randomUUID: () => "uuid",
    });
  });

  it("stores the rotated access + refresh tokens", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ access_token: "access-new", refresh_token: "refresh-new" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await changePassword({
      current_password: "old-pass1",
      password: "new-pass1",
      password_confirmation: "new-pass1",
    });

    expect(getAccessToken()).toBe("access-new");
    expect(stored).toBe("refresh-new");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://test/api/auth/change-password");
    expect(new Headers(options.headers).get("X-Client")).toBe("mobile");
  });
});
