import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../../shared/api";
import { UPLOAD_AVATAR_MAX_BYTES } from "../../../shared/lib/policy";
import { track } from "../../../shared/lib/track";
import { EVENTS } from "../../../shared/lib/events";
import { useMyCommunity } from "../api/hooks";
import { communityKeys } from "../api/keys";
import type { CommunityProfile } from "../model/types";
import ProfileEditor from "./ProfileEditor";

vi.mock("../../../shared/api", async (original) => ({
  ...(await original<typeof import("../../../shared/api")>()),
  api: vi.fn(),
}));
vi.mock("../../../shared/lib/track", () => ({ track: vi.fn() }));
const initial: CommunityProfile = {
  id: "p1",
  handle: "jane",
  display_name: "Jane Doe",
  bio: "Hello",
  avatar_url: "/api/files/old/content",
  created_at: "2026-01-01",
};
let profile: CommunityProfile;
const storage = vi.fn();
beforeEach(() => {
  vi.resetAllMocks();
  profile = { ...initial };
  vi.stubGlobal("fetch", storage);
  storage.mockResolvedValue({ ok: true });
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/community/me") return { profile, membership: null };
    if (path === "/files/uploads")
      return {
        file_id: "new",
        upload: {
          url: "https://storage.example/upload",
          method: "PUT",
          headers: { "Content-Type": "image/png" },
        },
      };
    if (path === "/files/new/confirm")
      return { id: "new", url: "/api/files/new/content", status: "ready" };
    if (path === "/community/profile/avatar") {
      profile = {
        ...profile,
        avatar_url: options?.method === "DELETE" ? null : "/api/files/new/content",
      };
      return options?.method === "DELETE" ? undefined : profile;
    }
    if (path === "/community/profile") {
      profile = { ...profile, ...JSON.parse(options?.body as string) };
      return profile;
    }
    throw new Error("Unexpected endpoint " + path);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Harness() {
  const { data } = useMyCommunity();
  return data?.profile ? <ProfileEditor profile={data.profile} /> : null;
}
function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(communityKeys.me, { profile, membership: null });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const view = render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>,
  );
  return { ...view, invalidate };
}
function choose(file = new File(["photo"], "photo.png", { type: "image/png" })) {
  fireEvent.change(screen.getByLabelText("Upload photo"), { target: { files: [file] } });
}
function uploads() {
  return vi.mocked(api).mock.calls.filter(([path]) => path === "/files/uploads");
}

it("shows a size error without calling the api", () => {
  setup();
  choose(
    new File([new Uint8Array(UPLOAD_AVATAR_MAX_BYTES + 1)], "large.png", { type: "image/png" }),
  );
  expect(screen.getByRole("alert")).toHaveTextContent(
    `${UPLOAD_AVATAR_MAX_BYTES / (1024 * 1024)} MB`,
  );
  expect(api).not.toHaveBeenCalled();
});
it("shows a type error without calling the api", () => {
  setup();
  choose(new File(["gif"], "photo.gif", { type: "image/gif" }));
  expect(screen.getByRole("alert")).toHaveTextContent("PNG, JPEG, or WebP");
  expect(api).not.toHaveBeenCalled();
});
it("uploads and then sets the profile avatar", async () => {
  const { container, invalidate } = setup();
  choose();
  await screen.findByText("Photo updated.");
  const paths = vi.mocked(api).mock.calls.map(([path]) => path);
  expect(paths.slice(0, 3)).toEqual([
    "/files/uploads",
    "/files/new/confirm",
    "/community/profile/avatar",
  ]);
  expect(api).toHaveBeenCalledWith("/community/profile/avatar", {
    method: "PUT",
    body: JSON.stringify({ file_id: "new" }),
  });
  expect(container.querySelector("img")).toHaveAttribute("src", "/api/files/new/content");
  expect(invalidate).toHaveBeenCalledWith({ queryKey: communityKeys.all });
});
it("tracks avatar_uploaded once on success", async () => {
  setup();
  choose();
  await screen.findByText("Photo updated.");
  expect(track).toHaveBeenCalledExactlyOnceWith(EVENTS.avatar_uploaded, { file_id: "new" });
});
it("disables the picker while uploading", async () => {
  let finish!: (value: { ok: boolean }) => void;
  storage.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  setup();
  choose();
  await waitFor(() => expect(storage).toHaveBeenCalledTimes(1));
  expect(screen.getByLabelText("Upload photo")).toBeDisabled();
  choose();
  expect(uploads()).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Save profile" })).toBeDisabled();
  finish({ ok: true });
  await screen.findByText("Photo updated.");
  expect(screen.getByLabelText("Upload photo")).toBeEnabled();
});
it("keeps the previous avatar when the upload fails", async () => {
  storage.mockResolvedValue({ ok: false, status: 503 });
  const { container } = setup();
  choose();
  await screen.findByText(/storage status 503/);
  expect(container.querySelector("img")).toHaveAttribute("src", initial.avatar_url);
  expect(api).not.toHaveBeenCalledWith("/community/profile/avatar", expect.anything());
  expect(track).not.toHaveBeenCalled();
});
it("removes the avatar", async () => {
  const { container, invalidate } = setup();
  fireEvent.click(screen.getByRole("button", { name: "Remove photo" }));
  await screen.findByText("Photo removed.");
  expect(api).toHaveBeenCalledWith("/community/profile/avatar", { method: "DELETE" });
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByText("JD")).toBeInTheDocument();
  expect(invalidate).toHaveBeenCalledWith({ queryKey: communityKeys.all });
});
it("saving other profile fields does not send avatar_url when a photo is uploaded", async () => {
  setup();
  expect(screen.getByLabelText("Avatar URL (optional)")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Bio (optional)"), { target: { value: "Updated bio" } });
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
  await screen.findByText("Profile saved.");
  expect(api).toHaveBeenCalledWith("/community/profile", {
    method: "PATCH",
    body: JSON.stringify({ display_name: "Jane Doe", bio: "Updated bio" }),
  });
});
it("sends avatar_url when the external url field was edited", async () => {
  setup();
  fireEvent.change(screen.getByLabelText("Avatar URL (optional)"), {
    target: { value: "https://example.com/photo.png" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
  await screen.findByText("Profile saved.");
  expect(api).toHaveBeenCalledWith("/community/profile", {
    method: "PATCH",
    body: JSON.stringify({
      display_name: "Jane Doe",
      bio: "Hello",
      avatar_url: "https://example.com/photo.png",
    }),
  });
});
it("shows the quota error message and action step", async () => {
  const error = new ApiError(429, "ERR_FILE_006", "Too many");
  setup();
  vi.mocked(api).mockRejectedValueOnce(error);
  choose();
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(error.userMessage));
  expect(screen.getByRole("alert")).toHaveTextContent(error.actionStep);
});
