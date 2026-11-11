import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  useChangeMemberRole,
  useCreateOrg,
  useInviteMember,
  useOrgs,
  useRemoveMember,
  useRevokeInvitation,
} from "./hooks";
import { orgKeys } from "./keys";
import type { Invitation, Member, Org } from "../model/types";

vi.mock("./endpoints");

import * as endpoints from "./endpoints";

const mocked = vi.mocked(endpoints);

function makeContext() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidateSpy = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, invalidateSpy, wrapper };
}

const org: Org = {
  id: "o1",
  name: "Acme",
  slug: "acme",
  email_domain: null,
  created_at: "2026-01-01T00:00:00Z",
  role: "owner",
};
const member: Member = {
  id: "m1",
  user_id: "u1",
  email: "a@b.com",
  name: "A",
  role: "member",
  created_at: "2026-01-01T00:00:00Z",
};
const invitation: Invitation = {
  id: "i1",
  email: "a@b.com",
  role: "member",
  expires_at: "2026-02-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useOrgs", () => {
  it("lists the orgs", async () => {
    mocked.listOrgs.mockResolvedValue([org]);
    const { wrapper } = makeContext();

    const { result } = renderHook(() => useOrgs(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([org]);
    expect(mocked.listOrgs).toHaveBeenCalledTimes(1);
  });
});

describe("useCreateOrg", () => {
  it("creates an org and invalidates the org list", async () => {
    mocked.createOrg.mockResolvedValue(org);
    const { invalidateSpy, wrapper } = makeContext();

    const { result } = renderHook(() => useCreateOrg(), { wrapper });
    result.current.mutate({ name: "Acme", intended_use: "Fraud prevention" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.createOrg.mock.calls[0][0]).toEqual({
      name: "Acme",
      intended_use: "Fraud prevention",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.all });
  });

  it("refetches the org list after creation (invalidation triggers a second fetch)", async () => {
    mocked.listOrgs.mockResolvedValue([org]);
    mocked.createOrg.mockResolvedValue(org);
    const { wrapper } = makeContext();

    const list = renderHook(() => useOrgs(), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    expect(mocked.listOrgs).toHaveBeenCalledTimes(1);

    const create = renderHook(() => useCreateOrg(), { wrapper });
    create.result.current.mutate({ name: "Acme", intended_use: "Analytics" });
    await waitFor(() => expect(create.result.current.isSuccess).toBe(true));

    // The active org-list observer refetches once invalidated.
    await waitFor(() => expect(mocked.listOrgs).toHaveBeenCalledTimes(2));
  });
});

describe("membership mutations", () => {
  it("useInviteMember invalidates members + invitations", async () => {
    mocked.createInvitation.mockResolvedValue(invitation);
    const { invalidateSpy, wrapper } = makeContext();

    const { result } = renderHook(() => useInviteMember("o1"), { wrapper });
    result.current.mutate({ email: "a@b.com", role: "member" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.createInvitation).toHaveBeenCalledWith("o1", "a@b.com", "member");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.members("o1") });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.invitations("o1") });
  });

  it("useChangeMemberRole invalidates members + invitations", async () => {
    mocked.changeMemberRole.mockResolvedValue(member);
    const { invalidateSpy, wrapper } = makeContext();

    const { result } = renderHook(() => useChangeMemberRole("o1"), { wrapper });
    result.current.mutate({ membershipId: "m1", role: "admin" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.changeMemberRole).toHaveBeenCalledWith("o1", "m1", "admin");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.members("o1") });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.invitations("o1") });
  });

  it("useRemoveMember invalidates members + invitations", async () => {
    mocked.removeMember.mockResolvedValue(undefined);
    const { invalidateSpy, wrapper } = makeContext();

    const { result } = renderHook(() => useRemoveMember("o1"), { wrapper });
    result.current.mutate("m1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.removeMember).toHaveBeenCalledWith("o1", "m1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.members("o1") });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.invitations("o1") });
  });

  it("useRevokeInvitation invalidates members + invitations", async () => {
    mocked.revokeInvitation.mockResolvedValue(undefined);
    const { invalidateSpy, wrapper } = makeContext();

    const { result } = renderHook(() => useRevokeInvitation("o1"), { wrapper });
    result.current.mutate("i1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.revokeInvitation).toHaveBeenCalledWith("o1", "i1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.members("o1") });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: orgKeys.invitations("o1") });
  });
});
