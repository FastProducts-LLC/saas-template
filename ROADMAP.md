# Roadmap

Known gaps and planned follow-ups. Pull requests are welcome; for anything
bigger than a small fix, open an issue first so we can agree on the approach.

## Community module

- Mobile (Expo) parity for the community slice, which is web-only for now.
- Message history beyond the latest page in the web thread view. Backend
  keyset pagination via `?before=` already works.
- Per-user rate-limit key for message sends (slowapi is IP-keyed today).
- Groups/forums: `community_conversations.type` is ready for a `group` value;
  the participants/messages tables need no changes.

## Billing, storage, and entitlements

- Mark `object-storage`, `subscription-billing`, and `entitlements` as
  `included` in `frontend/src/features/saas-features/model/featureCatalog.ts`
  (they have shipped) and update the `"filters by blueprint status"`
  assertions in `SaasFeaturesPage.test.tsx` in the same change.
- Per-seat subscription pricing: checkout uses quantity 1, and member changes
  do not update the Stripe subscription quantity.
- Organization-owned upload purposes, and object cleanup on organization
  deletion. The file facade has `delete_all_for_org`, but `DeleteOrganization`
  only deletes the org row; generated objects also need cleanup.
- Extend `backend/scripts/migrate_media_to_storage.py` to migrate uploaded
  files; it copies only generation assets today.
- Make failed avatar-object deletion retryable. The file facade logs provider
  failures but still removes the metadata row.
