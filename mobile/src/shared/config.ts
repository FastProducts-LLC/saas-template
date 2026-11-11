// API base URL resolution, in priority order:
//   1. EXPO_PUBLIC_API_URL (set for staging/production builds)
//   2. the Metro dev-server host — in `expo start` the dev machine's IP, so a
//      physical device on the same LAN reaches the Docker backend (:21428)
//      with zero configuration
//   3. platform loopback (Android emulators see the host as 10.0.2.2)

import Constants from "expo-constants";
import { Platform } from "react-native";

const API_PORT = 21428;

export function resolveApiBaseUrl(): string {
  const explicit = process.env.EXPO_PUBLIC_API_URL;
  if (explicit) return `${explicit.replace(/\/+$/, "")}/api`;
  const host = Constants.expoConfig?.hostUri?.split(":")[0];
  if (host) return `http://${host}:${API_PORT}/api`;
  const loopback = Platform.OS === "android" ? "10.0.2.2" : "localhost";
  return `http://${loopback}:${API_PORT}/api`;
}
