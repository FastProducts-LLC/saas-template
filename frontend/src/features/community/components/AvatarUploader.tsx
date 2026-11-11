import { useRef, useState } from "react";
import { ApiError } from "../../../shared/api";
import { Alert, Avatar, Button, Input, ErrorAlert } from "../../../shared/ui";
import {
  AVATAR_FILE_TYPES,
  AVATAR_VALIDATION_MESSAGES,
  useUploadFile,
  validateAvatarFile,
} from "../../files";
import { useRemoveAvatar, useSetAvatar } from "../api/hooks";
import type { CommunityProfile } from "../model/types";

interface Props {
  profile: CommunityProfile;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onChanged?: () => void;
}

export default function AvatarUploader({ profile, disabled, onBusyChange, onChanged }: Props) {
  const upload = useUploadFile("avatar");
  const setAvatar = useSetAvatar();
  const remove = useRemoveAvatar();
  const locked = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function run(file?: File) {
    if (locked.current || disabled) return;
    setError(null);
    setStatus(null);
    if (file) {
      const validation = validateAvatarFile(file);
      if (!validation.ok) {
        setError(AVATAR_VALIDATION_MESSAGES[validation.reason]);
        return;
      }
    }
    locked.current = true;
    setBusy(true);
    onBusyChange?.(true);
    setStatus(file ? "Uploading photo…" : "Removing photo…");
    try {
      if (file) {
        const confirmed = await upload.mutateAsync(file);
        await setAvatar.mutateAsync(confirmed.id);
      } else {
        await remove.mutateAsync();
      }
      onChanged?.();
      setStatus(file ? "Photo updated." : "Photo removed.");
    } catch (err) {
      setStatus(null);
      // ApiErrors render with catalog copy + ref; local upload errors
      // (thrown by the uploader itself) carry their own user-facing text.
      setError(
        err instanceof ApiError
          ? err
          : err instanceof Error
            ? err.message
            : "Photo update failed. Please try again.",
      );
    } finally {
      locked.current = false;
      setBusy(false);
      onBusyChange?.(false);
    }
  }

  return (
    <div className="space-y-3">
      <Avatar
        key={profile.avatar_url}
        name={profile.display_name}
        src={profile.avatar_url}
        size="lg"
      />
      <Input
        label="Upload photo"
        type="file"
        accept={AVATAR_FILE_TYPES.join(",")}
        disabled={busy || disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void run(file);
        }}
      />
      {profile.avatar_url && (
        <Button variant="danger" disabled={busy || disabled} onClick={() => void run()}>
          Remove photo
        </Button>
      )}
      {status && <Alert tone={busy ? "info" : "success"}>{status}</Alert>}
      <ErrorAlert error={error} />
    </div>
  );
}
