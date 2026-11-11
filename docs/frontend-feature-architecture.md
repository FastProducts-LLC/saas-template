# Frontend Refactor Targets

Known places where the frontend does not yet follow the feature-slice rules,
and how to fix them. Good starting points for contributors.

This frontend is currently a Vite + React Router app, not a Next.js App Router app. The feature layout below still maps cleanly to a future Next App Router migration: route files move to `app/**/page.tsx`, while feature code remains in `src/features/**`.

## Current State

The app already has a partial feature-based structure:

```text
frontend/src/
  App.tsx
  components/
    AppLayout.tsx
    ErrorBoundary.tsx
    OnboardingTour.tsx
    RequireAuth.tsx
  shared/
    api/
    lib/
    ui/
  features/
    admin/
    api-docs/
    api-keys/
    auth/
    billing/
    consent/
    credits/
    dashboard/
    home/
    legal/
    organizations/
```

The strongest slices are `credits`, `organizations`, `billing`, `api-keys`, and `consent`: they mostly separate endpoint functions, TanStack Query hooks, types, and UI. The main gap is inconsistent enforcement. Several components still import TanStack Query, call endpoint functions directly, own query invalidation, or contain domain transforms that should be in `model/`.

## Architecture Rules

1. `shared/api/client.ts` is transport infrastructure. It owns auth headers, refresh, idempotency keys, API error normalization, and retry behavior.
2. Feature endpoint functions live in `features/[feature]/api/endpoints.ts` and are the only feature code that imports `shared/api`.
3. TanStack Query and future Zustand stores are infrastructure. Components do not import `@tanstack/react-query`, `queryClient`, query keys, raw stores, or endpoint functions.
4. Components call domain hooks from `features/[feature]/api/hooks.ts` or thin feature facades exported from `features/[feature]/index.ts`.
5. Domain types, pure transforms, validators, grouping logic, and formatting decisions live in `features/[feature]/model/`.
6. Cross-feature imports use the other feature public API: `../../credits`, `../../organizations`, etc. No cross-feature import should reach into `../../credits/api/hooks` or `../../organizations/model/current-org`.
7. Shared UI remains generic. Feature-specific UI stays inside its feature.

## Target Directory Map

```text
frontend/src/
  App.tsx                         # Current React Router shell
  app/                            # Optional future route composition layer
    providers.tsx
    routes/
      AdminCustomersRoute.tsx     # Vite equivalent of Next app/admin/customers/page.tsx
      BillingRoute.tsx
  shared/
    api/
      client.ts                   # transport, auth refresh, ApiError
      errors.ts
      index.ts
    lib/
      analytics.ts
      brand.ts
      money.ts
      storage.ts
      tours.ts
    ui/
      Button.tsx
      Modal.tsx
      Alert.tsx
      ...
  features/
    auth/
      components/
        LoginPage.tsx
        RegisterPage.tsx
        ProfilePage.tsx
        PasswordRules.tsx
      api/
        endpoints.ts
        hooks.ts                  # add: profile/password/reset/verify domain hooks
        keys.ts                   # optional, if auth queries grow
      model/
        session.tsx
        password-policy.ts
        types.ts
      index.ts
    billing/
      components/
        BillingPage.tsx           # thin route adapter only
        BillingSummary.tsx
        CreditPackList.tsx
        CreditHistoryTable.tsx
        InvoicesSection.tsx
        UsageSection.tsx
      api/
        endpoints.ts
        hooks.ts
        keys.ts
      model/
        billing-page.ts           # derived page state, low balance, best value pack
        types.ts
      index.ts
    credits/
      components/
      api/
      model/
      index.ts
    organizations/
      components/
      api/
      model/
      index.ts
    api-keys/
      components/
        ApiKeysPage.tsx           # thin route adapter only
        ApiKeysTable.tsx
        CreateApiKeyDialog.tsx
        RevokeApiKeyDialog.tsx
        ApiKeySecretBanner.tsx
        ApiKeyQuickStart.tsx
      api/
        endpoints.ts
        hooks.ts
        keys.ts
      model/
        examples.ts               # curl example builder
        types.ts
      index.ts
    admin/
      components/
        AdminLayout.tsx
        AdminOverviewPage.tsx
        AdminCustomersPage.tsx    # thin route adapter only
        AdminCustomersView.tsx
        CustomersTable.tsx
        CustomerRow.tsx
        MergeOrganizationsDialog.tsx
        Pagination.tsx
        ...
      api/
        endpoints.ts
        hooks.ts
        keys.ts
      model/
        customer-groups.ts
        org-groups.ts
        compliance-items.ts
        types.ts
      index.ts
    api-docs/
      components/
        ApiDocsPage.tsx
        ApiDocsArticle.tsx
        ApiDocsToc.tsx
        MarkdownCodeBlock.tsx
      api/
        hooks.ts                  # useApiDocsMarkdown()
      model/
        markdown-parser.ts
        types.ts
      index.ts
```

For a strict "UI only components" standard, route files in `app/routes/` should call feature hooks and pass props into feature views. If the app keeps the current React Router layout, allow only `*Page.tsx` files to call domain hooks; all child components should be props-only.

## Components to refactor

High priority:

- `frontend/src/features/admin/AdminCustomersPage.tsx` is a god component. It combines domain grouping logic (`emailDomain`, `groupByDomain`), table and modal UI, local UI state, direct `useQuery`, direct `useMutation`, and `queryClient.invalidateQueries`.
- `frontend/src/features/admin/AdminOrgsPage.tsx` repeats the same grouping pattern and directly embeds a member query inside `OrgMembersRow`.
- `frontend/src/features/admin/api.ts` is overloaded. It contains API functions and all admin domain types in one flat file. Split it into `api/endpoints.ts`, `api/hooks.ts`, `api/keys.ts`, and `model/types.ts`.

Medium priority:

- `frontend/src/features/billing/components/BillingPage.tsx` is not directly coupled to raw endpoints, but it aggregates billing, credits, organization permissions, URL status side effects, page derivations, and several UI regions in one file.
- `frontend/src/features/api-keys/components/ApiKeysPage.tsx` correctly uses domain hooks, but still owns create/revoke orchestration, analytics, clipboard state, generated curl examples, table rendering, and both modals in one file.
- `frontend/src/features/auth/components/ProfilePage.tsx` imports endpoint functions directly and handles async mutation state inside UI sections.

Lower priority but worth splitting:

- `frontend/src/features/dashboard/components/DashboardPage.tsx` is a cross-feature composition page with tour config, view-model helpers, animation, and UI in one file.
- `frontend/src/features/api-docs/components/ApiDocsPage.tsx` mixes markdown parsing, inline rendering, static `fetch`, TOC derivation, and page chrome. Move parsing into `model/markdown-parser.ts` and static loading into `api/hooks.ts`.

## Boundary Chart

```text
auth
  Owns: session, login/register/reset/verify/profile operations, password policy
  Depends on: shared/api, shared/lib/analytics, shared/ui, consent public API for cookie settings
  Current gap: profile/reset/verify components call endpoints directly

organizations
  Owns: org list, current org selection, members, invitations, org permissions
  Depends on: shared/api, shared/lib/storage
  Current gap: mostly conforming

credits
  Owns: wallet, credit packs, history, usage, member limits, credit labels
  Depends on: shared/api, shared/lib/analytics
  Current gap: mostly conforming

billing
  Owns: billing account, portal, invoices, pricing page, billing UI
  Depends on: credits public API, organizations public API
  Current gap: page-level view model is embedded in BillingPage

api-keys
  Owns: API key list/create/revoke and key management UI
  Depends on: organizations public API, shared/api, shared/lib/analytics
  Current gap: page orchestration and presentational UI are not split

admin
  Owns: admin stats, analytics, customers, orgs, users, credits, audit, invitations, privacy requests
  Depends on: shared/api, auth public API for impersonation/session actions, organizations types
  Current gap: flat folder, direct TanStack Query usage in components, mixed API/types/UI

api-docs
  Owns: rendered API docs page and markdown parsing for local docs
  Depends on: home public API for marketing shell
  Current gap: parser and static fetch are embedded in UI component
```

## Refactoring Guide: AdminCustomersPage

Use `AdminCustomersPage` as the first complex-page conversion because it has every problem class: endpoint imports, direct query infrastructure, local mutation orchestration, domain grouping, UI tables, and modal UI.

### 1. Lock the baseline

Before any structural move:

```bash
docker compose run --rm frontend npm test
docker compose run --rm frontend npm run build
```

Record the number of passing specs and any pre-existing failures. Do not move files against a red suite.

### 2. Extract pure model logic first

Move these from `AdminCustomersPage.tsx` into `features/admin/model/customer-groups.ts`:

```text
SortKey
DomainGroup
emailDomain()
groupByDomain()
```

Rename `groupByDomain` to `groupCustomersByOwnerDomain` so the intent is clear and it can coexist with the org grouping logic. Add a focused unit test for the grouping behavior before changing page imports.

### 3. Split admin API infrastructure

Move `features/admin/api.ts` into:

```text
features/admin/model/types.ts
features/admin/api/endpoints.ts
features/admin/api/keys.ts
features/admin/api/hooks.ts
```

Suggested query key surface:

```ts
export const adminKeys = {
  all: ["admin"] as const,
  customers: (search: string, page: number, sort: SortKey) =>
    [...adminKeys.all, "customers", search, page, sort] as const,
  orgs: (search: string, page: number) =>
    [...adminKeys.all, "orgs", search, page] as const,
  orgMembers: (orgId: string) => [...adminKeys.all, "org-members", orgId] as const,
};
```

Suggested domain hooks:

```ts
export function useAdminCustomers(filters: AdminCustomerFilters) {
  return useQuery({
    queryKey: adminKeys.customers(filters.search, filters.page, filters.sort),
    queryFn: () => endpoints.listCustomers(filters.search, filters.page, filters.sort),
  });
}

export function useMergeOrganizations(cacheScope: "customers" | "orgs") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endpoints.mergeOrgs,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...adminKeys.all, cacheScope] });
    },
  });
}
```

The page should no longer import `@tanstack/react-query`, `queryClient`, `listCustomers`, or `mergeOrgs`.

### 4. Split page orchestration from presentational UI

Create a thin page adapter and a props-only view:

```text
features/admin/components/AdminCustomersPage.tsx
features/admin/components/AdminCustomersView.tsx
features/admin/components/CustomersTable.tsx
features/admin/components/CustomerRow.tsx
features/admin/components/MergeOrganizationsDialog.tsx
features/admin/components/SortableHeader.tsx
```

`AdminCustomersPage.tsx` should only wire hooks and derived state:

```tsx
export default function AdminCustomersPage() {
  const view = useAdminCustomersPage();
  return <AdminCustomersView {...view} />;
}
```

`useAdminCustomersPage()` can live in `features/admin/api/hooks.ts` if it mostly coordinates queries/mutations, or in `features/admin/model/use-admin-customers-page.ts` if it is mostly view-model state. Keep TanStack imports in `api/hooks.ts`.

### 5. Move UI pieces without changing behavior

Move one piece at a time:

1. `SortHeader` to `SortableHeader.tsx`.
2. `CustomerRow` to `CustomerRow.tsx`.
3. `MergeDialog` to `MergeOrganizationsDialog.tsx`.
4. Table body and empty/loading states to `CustomersTable.tsx`.
5. Remaining layout to `AdminCustomersView.tsx`.

After each move:

```bash
docker compose run --rm frontend npm test
```

Only after all moves are green, run:

```bash
docker compose run --rm frontend npm run build
```

### 6. Publish only the feature public API

Add `features/admin/index.ts`:

```ts
export { default as AdminLayout } from "./components/AdminLayout";
export { default as AdminCustomersPage } from "./components/AdminCustomersPage";
export { default as AdminOrgsPage } from "./components/AdminOrgsPage";
export { useAdminCustomers, useAdminOrgs } from "./api/hooks";
export type { AdminCustomerUsage, AdminOrg, Page } from "./model/types";
```

Then update route imports in `App.tsx` to use the public API or, if code splitting requires direct lazy imports, use direct imports only for page entry points and keep internals private.

### 7. Enforce import boundaries

Add lint rules or an import boundary check after the migration:

```text
components/ cannot import:
  @tanstack/react-query
  features/*/api/endpoints
  features/*/api/keys
  shared/api/client

features/* cannot import another feature internals:
  ../../other-feature/api/*
  ../../other-feature/model/*
  ../../other-feature/components/*
```

Allowed imports:

```text
features/admin/components/AdminCustomersPage.tsx -> ../api/hooks
features/admin/components/AdminCustomersView.tsx -> ../model/types
features/admin/api/hooks.ts -> ./endpoints, ./keys, ../model/types
features/admin/api/endpoints.ts -> ../../../shared/api, ../model/types
```

## Recommended Migration Order

1. Admin API split: `api.ts` into `api/endpoints.ts`, `api/hooks.ts`, `api/keys.ts`, `model/types.ts`.
2. Admin model split: customer/org grouping and compliance items into `model/`.
3. Admin component split: customers page, orgs page, users page, credits page, privacy requests page.
4. Auth mutation hooks: wrap profile, password, reset, forgot password, and email verification endpoint calls.
5. Billing page split: move pack selection, low-balance status, history pagination, and Stripe success refresh into a billing page hook/model.
6. API keys page split: extract table, dialogs, secret banner, and curl example builder.
7. API docs split: parser to model, markdown fetch hook to api, renderer components to components.
8. Dashboard split: tour config to model, stat/recent-activity UI to components, cross-feature aggregation to a page hook.

This sequence keeps infrastructure moves first, then pure model moves, then visual component moves. It minimizes behavioral risk and makes each commit easy to verify.
