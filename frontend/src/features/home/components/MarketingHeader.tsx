// Full-width top bar shared by the public marketing pages (home, pricing,
// docs, blog, legal). Anchor links are root-anchored ("/#how") so they work
// from any page: on the home page they only change the hash (smooth scroll),
// elsewhere they navigate home first.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { MK_WRAP, MkButton } from "../../../shared/ui/marketing";
import { useAuth } from "../../auth";
import BrandMark from "./BrandMark";

const NAV_LINK = "text-sm text-[var(--carbon)] transition-opacity hover:opacity-60";
const MOBILE_LINK = "py-1 text-base text-[var(--carbon)]";

export default function MarketingHeader() {
  const { user, loading } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [menuOpen]);

  return (
    <header
      data-testid="marketing-header"
      className={`mk fixed inset-x-0 top-0 z-30 border-b bg-[var(--canvas)]/90 backdrop-blur-md transition-colors duration-200 ${
        scrolled || menuOpen ? "border-[var(--mk-hair)]" : "border-transparent"
      }`}
    >
      <div className={`${MK_WRAP} flex h-16 items-center justify-between`}>
        <div className="flex items-center gap-10">
          <BrandMark
            variant="marketing"
            data-testid="marketing-header-logo-link"
            className="text-[var(--carbon)]"
          />
          <nav className="hidden items-center gap-7 md:flex">
            <a
              href={`${ROUTES.home}#features`}
              data-testid="marketing-header-features-link"
              className={NAV_LINK}
            >
              Features
            </a>
            <a
              href={`${ROUTES.home}#how`}
              data-testid="marketing-header-how-link"
              className={NAV_LINK}
            >
              How it works
            </a>
            <Link
              to={ROUTES.pricing}
              data-testid="marketing-header-pricing-link"
              className={NAV_LINK}
            >
              Pricing
            </Link>
            <Link to={ROUTES.docs} data-testid="marketing-header-docs-link" className={NAV_LINK}>
              API
            </Link>
            <Link
              to={ROUTES.blog.list}
              data-testid="marketing-header-blog-link"
              className={NAV_LINK}
            >
              Blog
            </Link>
            <a
              href={`${ROUTES.home}#faq`}
              data-testid="marketing-header-faq-link"
              className={NAV_LINK}
            >
              FAQ
            </a>
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {!loading && user ? (
            <MkButton to={ROUTES.dashboard} data-testid="marketing-header-dashboard-link">
              Dashboard
            </MkButton>
          ) : (
            <>
              <MkButton
                to={ROUTES.auth.login}
                variant="ghost"
                data-testid="marketing-header-login-link"
                className="max-sm:hidden"
              >
                Sign in
              </MkButton>
              <MkButton
                to={ROUTES.auth.register}
                data-testid="marketing-header-register-link"
                className="max-sm:hidden"
              >
                Get started
              </MkButton>
            </>
          )}
          {/* Mobile hamburger */}
          {!(user && !loading) && (
            <button
              type="button"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
              data-testid="marketing-header-menu-button"
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen((o) => !o);
              }}
              className="flex h-10 w-10 items-center justify-center rounded-md text-[var(--carbon)] transition-colors hover:bg-[var(--mk-chip)] md:hidden"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                {menuOpen ? (
                  <path
                    d="M5 5l10 10M15 5L5 15"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                ) : (
                  <path
                    d="M3 6h14M3 10h14M3 14h14"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                )}
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div
          data-testid="marketing-header-mobile-menu"
          className="border-t border-[var(--mk-hair)] bg-[var(--canvas)] px-6 py-5 md:hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <nav className="flex flex-col gap-2">
            <a
              href={`${ROUTES.home}#features`}
              data-testid="marketing-header-mobile-features-link"
              onClick={() => setMenuOpen(false)}
              className={MOBILE_LINK}
            >
              Features
            </a>
            <a
              href={`${ROUTES.home}#how`}
              data-testid="marketing-header-mobile-how-link"
              onClick={() => setMenuOpen(false)}
              className={MOBILE_LINK}
            >
              How it works
            </a>
            <Link
              to={ROUTES.pricing}
              data-testid="marketing-header-mobile-pricing-link"
              onClick={() => setMenuOpen(false)}
              className={MOBILE_LINK}
            >
              Pricing
            </Link>
            <Link
              to={ROUTES.docs}
              data-testid="marketing-header-mobile-docs-link"
              onClick={() => setMenuOpen(false)}
              className={MOBILE_LINK}
            >
              API docs
            </Link>
            <Link
              to={ROUTES.blog.list}
              data-testid="marketing-header-mobile-blog-link"
              onClick={() => setMenuOpen(false)}
              className={MOBILE_LINK}
            >
              Blog
            </Link>
            <a
              href={`${ROUTES.home}#faq`}
              data-testid="marketing-header-mobile-faq-link"
              onClick={() => setMenuOpen(false)}
              className={MOBILE_LINK}
            >
              FAQ
            </a>
            <div className="mt-3 flex flex-col gap-2 border-t border-[var(--mk-hair)] pt-4">
              <Link
                to={ROUTES.auth.login}
                data-testid="marketing-header-mobile-login-link"
                onClick={() => setMenuOpen(false)}
                className="rounded-md border border-[var(--mk-hair)] px-4 py-3 text-center text-sm text-[var(--carbon)]"
              >
                Sign in
              </Link>
              <Link
                to={ROUTES.auth.register}
                data-testid="marketing-header-mobile-register-link"
                onClick={() => setMenuOpen(false)}
                className="rounded-md bg-[var(--lime)] px-4 py-3 text-center text-sm text-[var(--carbon)] hover:bg-[var(--lime-deep)]"
              >
                Get started
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
