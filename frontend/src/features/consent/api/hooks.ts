/** Domain hook owning the consent lifecycle: local record, cross-device
 *  reconcile, and best-effort backend audit sync. Components only render. */

import { useCallback, useEffect, useState } from "react";

import {
  denyAnalyticsConsent,
  grantAnalyticsConsent,
  loadAnalytics,
} from "../../../shared/lib/track";
import { useAuth } from "../../auth";
import { fetchServerConsent, recordServerConsent } from "./endpoints";
import { CONSENT_VERSION, getStoredConsent, storeConsent } from "../model/store";

import type { ConsentCategories, StoredConsent } from "../model/types";

export function useCookieConsent() {
  const { user } = useAuth();
  const [record, setRecord] = useState<StoredConsent | null>(() => getStoredConsent());

  // Enact the choice: update Consent Mode v2 state and load the tag after a
  // grant (returning visitor or fresh commit). Withdrawal can't unload an
  // already-running script — the durable effect is that it won't load on the
  // next page load and consent reverts to denied.
  useEffect(() => {
    if (!record) return;
    if (record.categories.analytics) {
      grantAnalyticsConsent();
      loadAnalytics();
    } else {
      denyAnalyticsConsent();
    }
  }, [record]);
  // Undecided + signed in → hold the banner until the server is checked for
  // this user, so a choice made on another device wins instead of re-prompting.
  const [serverConsentCheckedFor, setServerConsentCheckedFor] = useState<string | null>(null);
  const pendingServerConsent = record === null && !!user && serverConsentCheckedFor !== user.id;

  useEffect(() => {
    if (!pendingServerConsent) return;
    let cancelled = false;
    const checkedUserId = user.id;
    fetchServerConsent()
      .then((server) => {
        if (cancelled || !server || server.policy_version !== CONSENT_VERSION) return;
        setRecord(storeConsent({ analytics: server.analytics }));
      })
      .catch(() => {
        // Offline / expired session — fall back to showing the banner.
      })
      .finally(() => {
        if (!cancelled) setServerConsentCheckedFor(checkedUserId);
      });
    return () => {
      cancelled = true;
    };
  }, [pendingServerConsent, user]);

  const commit = useCallback(
    (categories: ConsentCategories) => {
      setRecord(storeConsent(categories));
      if (user) {
        // Best-effort: the audit row is provability, not a gate — the local
        // record already took effect.
        recordServerConsent(categories, CONSENT_VERSION).catch(() => {});
      }
    },
    [user],
  );

  return {
    record,
    showBanner: record === null && !pendingServerConsent,
    commit,
  };
}
