// Organization context: which tenant the UI is currently operating in.
// The selected org id persists in localStorage across sessions.

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { getStoredOrgId, setStoredOrgId } from "../../../shared/lib/storage";
import { useOrgs } from "../api/hooks";
import type { Org } from "./types";

interface OrgContextValue {
  orgs: Org[];
  loading: boolean;
  currentOrg: Org | null;
  setCurrentOrgId: (orgId: string) => void;
}

const OrgContext = createContext<OrgContextValue | null>(null);

export function OrgProvider({ children }: { children: ReactNode }) {
  const { data: orgs = [], isLoading } = useOrgs();
  const [currentOrgId, setCurrentOrgIdState] = useState<string | null>(getStoredOrgId);

  const currentOrg = orgs.find((o) => o.id === currentOrgId) ?? orgs[0] ?? null;

  // Persist the effective org when we fall back (stored id missing/stale) so
  // the next session restores it. State needs no adjustment — `currentOrg` is
  // derived with the fallback built in, so render output is already correct.
  useEffect(() => {
    if (currentOrg && currentOrg.id !== currentOrgId) {
      setStoredOrgId(currentOrg.id);
    }
  }, [currentOrg, currentOrgId]);

  const setCurrentOrgId = (orgId: string) => {
    setCurrentOrgIdState(orgId);
    setStoredOrgId(orgId);
  };

  return (
    <OrgContext.Provider value={{ orgs, loading: isLoading, currentOrg, setCurrentOrgId }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg(): OrgContextValue {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg must be used within OrgProvider");
  return ctx;
}
