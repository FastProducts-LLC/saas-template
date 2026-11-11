import type { ReactNode } from "react";

import { act, cleanup, render, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OrgProvider, useOrg } from "./current-org";
import type { Org } from "./types";

// Mock the storage boundary so we can assert reads/writes without touching
// real localStorage, and the api/hooks boundary so OrgProvider gets a
// controlled org list (cleaner than mocking the fetch layer + QueryClient).
vi.mock("../../../shared/lib/storage", () => ({
  getStoredOrgId: vi.fn(),
  setStoredOrgId: vi.fn(),
  clearStoredOrgId: vi.fn(),
}));

vi.mock("../api/hooks", () => ({
  useOrgs: vi.fn(),
}));

import { getStoredOrgId, setStoredOrgId } from "../../../shared/lib/storage";
import { useOrgs } from "../api/hooks";

const mockedGetStoredOrgId = vi.mocked(getStoredOrgId);
const mockedSetStoredOrgId = vi.mocked(setStoredOrgId);
const mockedUseOrgs = vi.mocked(useOrgs);

function org(id: string, name = id): Org {
  return {
    id,
    name,
    slug: name,
    email_domain: null,
    created_at: "2026-01-01T00:00:00Z",
    role: "owner",
  };
}

type UseOrgsResult = ReturnType<typeof useOrgs>;

function setOrgs(orgs: Org[], isLoading = false) {
  mockedUseOrgs.mockReturnValue({ data: orgs, isLoading } as unknown as UseOrgsResult);
}

const wrapper = ({ children }: { children: ReactNode }) => <OrgProvider>{children}</OrgProvider>;

function Probe() {
  const { currentOrg } = useOrg();
  return <span>{currentOrg?.id ?? "none"}</span>;
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("OrgProvider", () => {
  const orgs = [org("o1"), org("o2"), org("o3")];

  it("selects the stored org when it is present in the list", () => {
    mockedGetStoredOrgId.mockReturnValue("o2");
    setOrgs(orgs);

    const { result } = renderHook(() => useOrg(), { wrapper });

    expect(result.current.currentOrg?.id).toBe("o2");
    expect(result.current.orgs).toHaveLength(3);
    // Stored id is current, so no persistence write is needed.
    expect(mockedSetStoredOrgId).not.toHaveBeenCalled();
  });

  it("falls back to the first org when the stored id is stale and persists it", () => {
    mockedGetStoredOrgId.mockReturnValue("does-not-exist");
    setOrgs(orgs);

    const { result } = renderHook(() => useOrg(), { wrapper });

    // currentOrg is derived with the fallback baked in...
    expect(result.current.currentOrg?.id).toBe("o1");
    // ...and the effect persists the fallback without calling setState.
    expect(mockedSetStoredOrgId).toHaveBeenCalledWith("o1");
  });

  it("falls back to the first org when nothing is stored", () => {
    mockedGetStoredOrgId.mockReturnValue(null);
    setOrgs(orgs);

    const { result } = renderHook(() => useOrg(), { wrapper });

    expect(result.current.currentOrg?.id).toBe("o1");
    expect(mockedSetStoredOrgId).toHaveBeenCalledWith("o1");
  });

  it("setCurrentOrgId updates state and writes to storage", () => {
    mockedGetStoredOrgId.mockReturnValue("o1");
    setOrgs(orgs);

    const { result } = renderHook(() => useOrg(), { wrapper });
    expect(result.current.currentOrg?.id).toBe("o1");

    act(() => result.current.setCurrentOrgId("o3"));

    expect(result.current.currentOrg?.id).toBe("o3");
    expect(mockedSetStoredOrgId).toHaveBeenCalledWith("o3");
  });

  it("passes the loading flag through", () => {
    mockedGetStoredOrgId.mockReturnValue(null);
    setOrgs([], true);

    const { result } = renderHook(() => useOrg(), { wrapper });

    expect(result.current.loading).toBe(true);
    expect(result.current.currentOrg).toBeNull();
  });
});

describe("useOrg", () => {
  it("throws when used outside an OrgProvider", () => {
    // Silence React's error-boundary console noise for the expected throw.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow("useOrg must be used within OrgProvider");
    spy.mockRestore();
  });
});
