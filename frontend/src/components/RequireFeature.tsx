// Route guard for admin-toggleable modules. Mirrors the backend's
// require_feature() gate: a disabled feature renders as Not Found, so the
// route is indistinguishable from one that doesn't exist. The guard here is
// cosmetic — the backend 404s the API calls regardless.

import { Outlet } from "react-router-dom";

import { useFeature } from "../features/config";
import type { FeatureKey } from "../features/config";
import NotFoundPage from "../features/home/NotFoundPage";
import FullScreenSpinner from "../shared/ui/FullScreenSpinner";

export default function RequireFeature({ flag }: { flag: FeatureKey }) {
  const enabled = useFeature(flag);

  if (enabled === undefined) {
    return <FullScreenSpinner />;
  }
  if (!enabled) {
    return <NotFoundPage />;
  }
  return <Outlet />;
}
