import { useCallback, useEffect, useState } from "react";
import type { OnboardingStep } from "./OnboardingTour";

const SEEN = "true";

export type TourStatus = "completed" | "skipped";

export interface TourStorage {
  seen(key: string): boolean | Promise<boolean>;
  markSeen(key: string, status: TourStatus): void | Promise<void>;
  reset(key: string): void | Promise<void>;
}

export const localTourStorage: TourStorage = {
  seen(key) {
    try {
      return localStorage.getItem(key) === SEEN;
    } catch {
      return false;
    }
  },
  markSeen(key) {
    try {
      localStorage.setItem(key, SEEN);
    } catch {
      /* storage unavailable */
    }
  },
  reset(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
};

export interface UseTourOptions {
  enabled?: boolean;
  delayMs?: number;
  waitForTarget?: boolean;
  storage?: TourStorage;
}

export interface TourControls {
  isOpen: boolean;
  steps: OnboardingStep[];
  onClose: () => void;
  onComplete: () => void;
  replay: () => void;
}

export function useTour(
  key: string,
  steps: OnboardingStep[],
  options: UseTourOptions = {},
): TourControls {
  const {
    enabled = true,
    delayMs = 600,
    waitForTarget = true,
    storage = localTourStorage,
  } = options;

  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;

    const open = () => {
      if (!cancelled) setIsOpen(true);
    };

    Promise.resolve(storage.seen(key)).then((alreadySeen) => {
      if (cancelled || alreadySeen) return;
      const firstSelector = steps.find((s) => s.selector)?.selector;
      if (waitForTarget && firstSelector) {
        cleanup = onElementReady(firstSelector, open, delayMs * 10);
      } else {
        const t = window.setTimeout(open, delayMs);
        cleanup = () => window.clearTimeout(t);
      }
    });

    return () => {
      cancelled = true;
      cleanup?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  const finish = useCallback(
    (status: TourStatus) => {
      setIsOpen(false);
      void storage.markSeen(key, status);
    },
    [key, storage],
  );

  const replay = useCallback(() => setIsOpen(true), []);

  return {
    isOpen,
    steps,
    onComplete: () => finish("completed"),
    onClose: () => finish("skipped"),
    replay,
  };
}

function onElementReady(selector: string, cb: () => void, timeoutMs: number): () => void {
  if (typeof document === "undefined") return () => {};
  if (document.querySelector(selector)) {
    cb();
    return () => {};
  }

  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    observer.disconnect();
    window.clearTimeout(timer);
    cb();
  };

  const observer = new MutationObserver(() => {
    if (document.querySelector(selector)) finish();
  });
  observer.observe(document.body, { childList: true, subtree: true });
  const timer = window.setTimeout(finish, timeoutMs);

  return () => {
    done = true;
    observer.disconnect();
    window.clearTimeout(timer);
  };
}
