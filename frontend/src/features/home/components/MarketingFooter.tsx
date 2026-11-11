// Dark multi-column footer shared by the public marketing pages.

import { Link } from "react-router-dom";

import { useAuth } from "../../auth";
import { openCookieSettings } from "../../consent";
import { ROUTES } from "../../../shared/lib/routes";
import { BRAND_LEGAL } from "../../../shared/lib/brand";
import BrandMark from "./BrandMark";

export default function MarketingFooter() {
  const { user } = useAuth();
  const primaryHref = user ? ROUTES.dashboard : ROUTES.auth.register;

  return (
    <footer data-testid="marketing-footer" className="mk bg-[var(--carbon)] text-white">
      <div className="mx-auto w-full max-w-[1360px] px-6 py-16 md:px-10 lg:px-16">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <BrandMark
              variant="marketing"
              data-testid="marketing-footer-logo-link"
              className="text-white"
            />
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-white/60">
              A multi-tenant SaaS starter with billing, credits, and metered AI built in.
            </p>
          </div>
          <div>
            <p className="text-sm text-white">Product</p>
            <ul className="mt-3 space-y-2.5 text-sm text-white/60">
              <li>
                <a
                  href={`${ROUTES.home}#features`}
                  data-testid="marketing-footer-features-link"
                  className="transition-colors hover:text-white"
                >
                  Features
                </a>
              </li>
              <li>
                <a
                  href={`${ROUTES.home}#how`}
                  data-testid="marketing-footer-how-link"
                  className="transition-colors hover:text-white"
                >
                  How it works
                </a>
              </li>
              <li>
                <Link
                  to={ROUTES.pricing}
                  data-testid="marketing-footer-pricing-link"
                  className="transition-colors hover:text-white"
                >
                  Pricing
                </Link>
              </li>
              <li>
                <Link
                  to={ROUTES.docs}
                  data-testid="marketing-footer-docs-link"
                  className="transition-colors hover:text-white"
                >
                  API docs
                </Link>
              </li>
              <li>
                <Link
                  to={ROUTES.blog.list}
                  data-testid="marketing-footer-blog-link"
                  className="transition-colors hover:text-white"
                >
                  Blog
                </Link>
              </li>
              <li>
                <a
                  href={`${ROUTES.home}#faq`}
                  data-testid="marketing-footer-faq-link"
                  className="transition-colors hover:text-white"
                >
                  FAQ
                </a>
              </li>
            </ul>
          </div>
          <div>
            <p className="text-sm text-white">Account</p>
            <ul className="mt-3 space-y-2.5 text-sm text-white/60">
              <li>
                <Link
                  to={ROUTES.auth.login}
                  data-testid="marketing-footer-login-link"
                  className="transition-colors hover:text-white"
                >
                  Sign in
                </Link>
              </li>
              <li>
                <Link
                  to={primaryHref}
                  data-testid="marketing-footer-cta-link"
                  className="transition-colors hover:text-white"
                >
                  {user ? "Dashboard" : "Get started"}
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="text-sm text-white">Legal</p>
            <ul className="mt-3 space-y-2.5 text-sm text-white/60">
              <li>
                <Link
                  to={ROUTES.legal.terms}
                  data-testid="marketing-footer-terms-link"
                  className="transition-colors hover:text-white"
                >
                  Terms
                </Link>
              </li>
              <li>
                <Link
                  to={ROUTES.legal.privacy}
                  data-testid="marketing-footer-privacy-link"
                  className="transition-colors hover:text-white"
                >
                  Privacy
                </Link>
              </li>
              <li>
                <button
                  type="button"
                  onClick={openCookieSettings}
                  data-testid="marketing-footer-cookie-settings-button"
                  className="transition-colors hover:text-white"
                >
                  Cookie settings
                </button>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-white/10 pt-6 text-sm text-white/50">
          <p>
            © {new Date().getFullYear()} {BRAND_LEGAL}. All rights reserved.
          </p>
          <div className="flex gap-5">
            <Link
              to={ROUTES.legal.terms}
              data-testid="marketing-footer-bottom-terms-link"
              className="transition-colors hover:text-white"
            >
              Terms of Service
            </Link>
            <Link
              to={ROUTES.legal.privacy}
              data-testid="marketing-footer-bottom-privacy-link"
              className="transition-colors hover:text-white"
            >
              Privacy Policy
            </Link>
            <button
              type="button"
              onClick={openCookieSettings}
              data-testid="marketing-footer-bottom-cookie-settings-button"
              className="transition-colors hover:text-white"
            >
              Cookie settings
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
