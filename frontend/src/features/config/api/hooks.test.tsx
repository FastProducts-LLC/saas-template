import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useConfig, useFeature } from "./hooks";
import type { AppConfig } from "../model/types";

vi.mock("./endpoints");

import * as endpoints from "./endpoints";

const mocked = vi.mocked(endpoints);

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return wrapper;
}

const config: AppConfig = { features: { community: true } };

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useConfig", () => {
  it("fetches the public config", async () => {
    mocked.getConfig.mockResolvedValue(config);

    const { result } = renderHook(() => useConfig(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(config);
  });
});

describe("useFeature", () => {
  it("is undefined while loading, then the flag value", async () => {
    mocked.getConfig.mockResolvedValue(config);

    const { result } = renderHook(() => useFeature("community"), {
      wrapper: makeWrapper(),
    });

    expect(result.current).toBeUndefined();
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("treats a missing key as off", async () => {
    mocked.getConfig.mockResolvedValue({ features: {} });

    const { result } = renderHook(() => useFeature("community"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current).toBe(false));
  });
});
