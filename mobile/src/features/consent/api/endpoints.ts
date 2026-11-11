import { api } from "../../../shared/api";
import { CONSENT_VERSION, type Consent } from "../model/types";

export const getConsent = () => api<Consent | null>("/consent");

export const recordConsent = (analytics: boolean) =>
  api<Consent>("/consent", {
    method: "POST",
    body: JSON.stringify({ analytics, policy_version: CONSENT_VERSION }),
  });
