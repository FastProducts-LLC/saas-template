import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../../../shared/api";
import { putToStorage } from "./endpoints";
import { useUploadFile } from "./hooks";

vi.mock("../../../shared/api", () => ({ api: vi.fn() }));
const file = new File(["bytes"], "photo.png", { type: "image/png" });
const target = {
  url: "https://storage.example/upload",
  method: "PUT",
  headers: { "Content-Type": "image/png" },
  expires_at: "2026-12-01",
};
const fetchMock = vi.fn();

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockResolvedValue({ ok: true });
});
afterEach(() => vi.unstubAllGlobals());

it("puts to an absolute url without credentials or auth headers", async () => {
  await putToStorage(target, file);
  expect(fetchMock).toHaveBeenCalledWith(target.url, {
    method: "PUT",
    headers: target.headers,
    body: file,
    credentials: "omit",
  });
  expect(new Headers(fetchMock.mock.calls[0][1].headers).has("authorization")).toBe(false);
  expect(api).not.toHaveBeenCalled();
});
it("puts to a relative api url with the returned headers", async () => {
  const relative = {
    ...target,
    url: "/api/files/local-upload/token",
    method: "POST",
    headers: { ...target.headers, "X-Upload": "grant" },
  };
  await putToStorage(relative, file);
  expect(fetchMock).toHaveBeenCalledWith(relative.url, {
    method: relative.method,
    headers: relative.headers,
    body: file,
    credentials: "omit",
  });
  expect(api).not.toHaveBeenCalled();
});
it("sends the returned content-type header", async () => {
  const upload = { ...target, headers: { "content-type": "application/octet-stream" } };
  await putToStorage(upload, file);
  expect(fetchMock.mock.calls[0][1].headers).toEqual(upload.headers);
});
it("rejects when storage responds with an error", async () => {
  fetchMock.mockResolvedValue({ ok: false, status: 503 });
  await expect(putToStorage(target, file)).rejects.toThrow("storage status 503");
});

function setup() {
  const client = new QueryClient();
  return renderHook(() => useUploadFile("avatar"), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

it("runs create, put and confirm in order", async () => {
  const order: string[] = [];
  const confirmed = { id: "f1", status: "ready" };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/files/uploads") {
      order.push("create");
      return { file_id: "f1", upload: target };
    }
    order.push("confirm");
    return confirmed;
  });
  fetchMock.mockImplementation(async () => {
    order.push("put");
    return { ok: true };
  });
  const { result } = setup();
  await act(async () => expect(await result.current.mutateAsync(file)).toEqual(confirmed));
  expect(order).toEqual(["create", "put", "confirm"]);
  expect(api).toHaveBeenCalledWith("/files/uploads", {
    method: "POST",
    body: JSON.stringify({ purpose: "avatar", content_type: file.type, size_bytes: file.size }),
  });
  expect(api).toHaveBeenLastCalledWith("/files/f1/confirm", { method: "POST" });
});

it.each(["put", "confirm"])("rejects if %s fails", async (step) => {
  vi.mocked(api)
    .mockResolvedValueOnce({ file_id: "f1", upload: target })
    .mockRejectedValueOnce(new Error("confirm failed"));
  if (step === "put") fetchMock.mockRejectedValueOnce(new Error("put failed"));
  const { result } = setup();
  await act(async () => {
    await expect(result.current.mutateAsync(file)).rejects.toThrow(step + " failed");
  });
  expect(api).toHaveBeenCalledTimes(step === "put" ? 1 : 2);
});
