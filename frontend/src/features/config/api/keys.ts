// Single source of truth for config cache identity. The admin flags page
// invalidates this after a toggle so nav/routes react without a reload.
export const configKeys = {
  all: ["config"] as const,
};
