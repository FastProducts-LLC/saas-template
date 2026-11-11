import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { Button, Modal } from "../../../shared/ui";
import { useCookieConsent } from "../api/hooks";
import { onOpenCookieSettings } from "../model/store";

import type { ConsentCategories } from "../model/types";

const ALL: ConsentCategories = { analytics: true };
const NONE: ConsentCategories = { analytics: false };

interface CategoryRowProps {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange?: (value: boolean) => void;
  "data-testid"?: string;
}

function CategoryRow({
  label,
  description,
  checked,
  disabled,
  onChange,
  "data-testid": dataTestId,
}: CategoryRowProps) {
  return (
    <label className="flex items-start gap-3 border-t border-[var(--line)] py-3 first:border-t-0">
      <input
        type="checkbox"
        data-testid={dataTestId}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-[var(--line)] accent-[var(--teal-deep)]"
      />
      <span>
        <span className="block text-sm font-semibold text-[var(--ink)]">
          {label}
          {disabled && (
            <span className="ml-2 text-xs font-medium text-[var(--slate)]">Always on</span>
          )}
        </span>
        <span className="mt-0.5 block text-sm text-[var(--slate)]">{description}</span>
      </span>
    </label>
  );
}

// Granular opt-in consent (ePrivacy/GDPR): appears until the visitor decides,
// re-openable later via openCookieSettings() (footer / profile). Essential is
// always on; Analytics defaults off and gates GA (shared/lib/analytics).
export default function CookieConsent() {
  const { record, showBanner, commit } = useCookieConsent();
  const [customizing, setCustomizing] = useState(false);
  const [draft, setDraft] = useState<ConsentCategories>(NONE);

  useEffect(
    () =>
      onOpenCookieSettings(() => {
        setDraft(record?.categories ?? NONE);
        setCustomizing(true);
      }),
    [record],
  );

  const decide = (categories: ConsentCategories) => {
    commit(categories);
    setCustomizing(false);
  };

  return (
    <>
      {showBanner && !customizing && (
        <div data-testid="cookie-banner" className="fixed inset-x-0 bottom-0 z-50 p-4">
          <div className="mx-auto flex max-w-3xl flex-col gap-3 rounded border border-[var(--line)] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-[var(--slate)]">
              We use essential cookies to keep you signed in and catch errors. Optional analytics
              runs only if you allow it — no personal data or user inputs are ever shared. See our{" "}
              <Link
                to={ROUTES.legal.privacy}
                data-testid="cookie-privacy-link"
                className="text-[var(--teal-deep)] underline underline-offset-2"
              >
                Privacy Policy
              </Link>
              .
            </p>
            <div className="flex shrink-0 gap-2">
              <Button
                variant="secondary"
                data-testid="cookie-preferences-button"
                onClick={() => {
                  setDraft(NONE);
                  setCustomizing(true);
                }}
              >
                Customize
              </Button>
              <Button
                variant="secondary"
                data-testid="cookie-reject-button"
                onClick={() => decide(NONE)}
              >
                Reject all
              </Button>
              <Button
                variant="primary"
                data-testid="cookie-accept-all-button"
                onClick={() => decide(ALL)}
              >
                Accept all
              </Button>
            </div>
          </div>
        </div>
      )}
      <Modal
        open={customizing}
        onClose={() => setCustomizing(false)}
        title="Cookie preferences"
        data-testid="cookie-preferences-modal"
        footer={
          <>
            <Button
              variant="secondary"
              data-testid="cookie-preferences-reject-button"
              onClick={() => decide(NONE)}
            >
              Reject all
            </Button>
            <Button
              variant="primary"
              data-testid="cookie-save-button"
              onClick={() => decide(draft)}
            >
              Save preferences
            </Button>
          </>
        }
      >
        <CategoryRow
          label="Essential"
          description="Sign-in session, security, error monitoring, and this consent choice. Required for the Service to operate."
          checked
          disabled
          data-testid="cookie-essential-checkbox"
        />
        <CategoryRow
          label="Analytics"
          data-testid="cookie-analytics-checkbox"
          description="Google Analytics for aggregate usage: page routes and which features are used. User inputs, query strings, and resource ids are never sent."
          checked={draft.analytics}
          onChange={(analytics) => setDraft((d) => ({ ...d, analytics }))}
        />
        <p className="mt-3 text-xs text-[var(--slate)]">
          Details in our{" "}
          <Link
            to={ROUTES.legal.privacy}
            data-testid="cookie-modal-privacy-link"
            className="text-[var(--teal-deep)] underline underline-offset-2"
          >
            Privacy Policy
          </Link>
          . Change your mind anytime via “Cookie settings” in the footer.
        </p>
      </Modal>
    </>
  );
}
