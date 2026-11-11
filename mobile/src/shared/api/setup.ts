// Composition root for the API client: wires the platform adapters
// (SecureStore, expo-crypto, resolved base URL) into the pure client module.
// Called once from the session provider before any request fires.

import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";

import { resolveApiBaseUrl } from "../config";
import { configureApi } from "./client";

const REFRESH_TOKEN_KEY = "refresh_token";

export function initApi(onSessionExpired?: () => void): void {
  configureApi({
    baseUrl: resolveApiBaseUrl(),
    randomUUID: () => Crypto.randomUUID(),
    refreshTokens: {
      get: () => SecureStore.getItemAsync(REFRESH_TOKEN_KEY),
      set: (token) =>
        token
          ? SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token)
          : SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY),
    },
    onSessionExpired,
  });
}
