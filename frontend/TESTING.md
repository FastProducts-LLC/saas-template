# Test automation hooks (`data-testid`)

> E2E suite: `frontend/e2e/` (Playwright, `npm run test:e2e`) — see
> `e2e/README.md` for stack requirements and rate-limit handling.

Every element an automated test needs to click, type into, or assert on carries a
`data-testid`. IDs are stable contracts: renaming one breaks test suites — treat
changes like API changes.

## Naming convention

Kebab-case, scoped by page/feature: `{scope}-{element}[-{qualifier}]`.

| What                            | Pattern                                               | Example                        |
| ------------------------------- | ----------------------------------------------------- | ------------------------------ |
| Page root container             | `{scope}-page`                                        | `login-page`, `records-page`   |
| Form                            | `{scope}-form`                                        | `login-form`                   |
| Text input                      | `{scope}-{field}-input`                               | `login-email-input`            |
| Select / checkbox               | `{scope}-{field}-select` / `-checkbox`                | `register-terms-checkbox`      |
| Submit button                   | `{scope}-submit`                                      | `register-submit`              |
| Other buttons                   | `{scope}-{action}-button`                             | `members-invite-button`        |
| Links used in flows             | `{scope}-{target}-link`                               | `login-forgot-link`            |
| Inline error / success          | `{scope}-error` / `{scope}-success`                   | `login-error`                  |
| Loading state                   | `{scope}-loading`                                     | `records-loading`              |
| Empty state                     | `{scope}-empty`                                       | `invoices-empty`               |
| Table / list                    | `{scope}-table` / `{scope}-list`                      | `members-table`                |
| Repeated row/item               | `{scope}-row` / `{scope}-item` + `data-id={entityId}` | `members-row` + `data-id="42"` |
| Modal dialog                    | `{scope}-{purpose}-modal`                             | `api-keys-revoke-modal`        |
| Final confirm button in a modal | `{scope}-{purpose}-confirm`                           | `api-keys-revoke-confirm`      |

Rules:

- **Static IDs only** — never interpolate entity ids into the testid itself.
  Rows get a constant `data-testid` plus a separate `data-id` attribute; tests
  select `[data-testid="members-row"][data-id="42"]`.
- Scope = the page or feature short name (`login`, `register`, `profile`,
  `records`, `record-detail`, `credits`, `billing`, `members`, `api-keys`,
  `admin-users`, …). Shared chrome uses `nav-`, `toast-`, `cookie-` scopes.
- Don't tag purely decorative elements. Prefer accessible selectors
  (`getByRole`, `getByLabelText`) in unit tests; `data-testid` exists for E2E
  automation and as a fallback where roles are ambiguous.

## Shared UI atoms

- `Button`, `Input`, `Card` extend native HTML props — pass `data-testid`
  directly.
- `Modal`, `Alert`, `PasswordInput`, `CopyButton` accept an explicit
  `data-testid` prop. `PasswordInput` also exposes `{testid}-toggle` on the
  show/hide button; `CopyButton` sets `data-copied` while flashing the check.
- `Alert` always exposes `data-tone="error|success|warning|info"`.
- `FullScreenSpinner` is always `data-testid="fullscreen-spinner"` — wait for
  it to detach before asserting page content.

## Global fixtures

- Onboarding tour: `onboarding-tour`, `onboarding-next-button`,
  `onboarding-skip-button`, `onboarding-close-button` (see `OnboardingTour.tsx`).
