import { useRef, useState, type FormEvent } from "react";
import {
  COMMUNITY_AVATAR_URL_MAX_LENGTH,
  COMMUNITY_BIO_MAX_LENGTH,
  COMMUNITY_DISPLAY_NAME_MAX_LENGTH,
} from "../../../shared/lib/policy";
import { Alert, Button, Input, Textarea, ErrorAlert } from "../../../shared/ui";
import { useUpdateProfile } from "../api/hooks";
import type { CommunityProfile } from "../model/types";
import AvatarUploader from "./AvatarUploader";

export default function ProfileEditor({ profile }: { profile: CommunityProfile }) {
  const update = useUpdateProfile();
  const [name, setName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio ?? "");
  const [url, setUrl] = useState(
    profile.avatar_url?.startsWith("https://") ? profile.avatar_url : "",
  );
  const [urlEdited, setUrlEdited] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const saving = useRef(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving.current || avatarBusy) return;
    saving.current = true;
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        display_name: name,
        bio: bio || null,
        ...(urlEdited ? { avatar_url: url.trim() || null } : {}),
      });
      setUrlEdited(false);
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      saving.current = false;
    }
  }

  return (
    <section className="mb-6 border-b border-[var(--line)] pb-6">
      <h2 className="mb-4 text-xl font-semibold text-[var(--ink)]">Your community profile</h2>
      <form onSubmit={(event) => void submit(event)} className="max-w-lg space-y-4">
        <AvatarUploader
          profile={profile}
          disabled={update.isPending}
          onBusyChange={setAvatarBusy}
          onChanged={() => {
            setUrl("");
            setUrlEdited(false);
            setSaved(false);
          }}
        />
        <Input
          label="Avatar URL (optional)"
          type="url"
          placeholder="https://"
          value={url}
          maxLength={COMMUNITY_AVATAR_URL_MAX_LENGTH}
          disabled={avatarBusy || update.isPending}
          onChange={(event) => {
            setUrl(event.target.value);
            setUrlEdited(true);
          }}
        />
        <Input
          label="Display name"
          value={name}
          required
          maxLength={COMMUNITY_DISPLAY_NAME_MAX_LENGTH}
          disabled={update.isPending}
          onChange={(event) => setName(event.target.value)}
        />
        <Textarea
          label="Bio (optional)"
          value={bio}
          maxLength={COMMUNITY_BIO_MAX_LENGTH}
          disabled={update.isPending}
          onChange={(event) => setBio(event.target.value)}
        />
        <Button type="submit" loading={update.isPending} disabled={avatarBusy}>
          Save profile
        </Button>
        {!!error && <ErrorAlert error={error} />}
        {saved && <Alert tone="success">Profile saved.</Alert>}
      </form>
    </section>
  );
}
