import { localTourStorage, type TourStorage } from "../../components/useTour";

const PREFIX = "app";

export const TOUR_KEYS = {
  dashboard: `${PREFIX}:tour-dashboard`,
} as const;

export type TourKey = (typeof TOUR_KEYS)[keyof typeof TOUR_KEYS];

export const TOUR_LABELS: Record<TourKey, string> = {
  [TOUR_KEYS.dashboard]: "Dashboard tour",
};

export function resetAllTours(storage: TourStorage = localTourStorage): void {
  Object.values(TOUR_KEYS).forEach((key) => {
    void storage.reset(key);
  });
}
