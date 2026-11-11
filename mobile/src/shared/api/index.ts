export {
  api,
  apiDataUri,
  ApiError,
  configureApi,
  getAccessToken,
  getStoredRefreshToken,
  setAccessToken,
  storeRefreshToken,
  tryRefresh,
  type ApiConfig,
  type RefreshTokenStore,
} from "./client";
export { publishError, subscribeErrors } from "./errorBus";
export {
  errorCatalog,
  formatErrorMessage,
  isErrorCode,
  type CatalogEntry,
  type ErrorCode,
  type ErrorParams,
} from "./errorCatalog";
export {
  claimError,
  fieldLabel,
  INLINE_CLAIM_GRACE_MS,
  isErrorClaimed,
} from "./errors";
// NOTE: initApi (the platform composition root) is deliberately NOT exported
// here — importing it drags expo-secure-store into every consumer, which
// breaks Node-side unit tests. The session provider imports ./setup directly.
