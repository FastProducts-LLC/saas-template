import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * Reads the one-time token an email link carries and scrubs it from the
 * address bar.
 *
 * Links put the token in the URL fragment (`/reset-password#token=...`):
 * fragments are never sent to a server, so the token stays out of access
 * logs, proxies and Referer headers. `?token=` is still accepted so emails
 * sent before the switch keep working.
 *
 * The token is captured once into state and then removed from the URL with a
 * history *replace*, so it doesn't linger in browser history or get copied
 * along when the user shares the page address.
 */
export function readLinkToken(hash: string, search: string): string {
  const fromHash = new URLSearchParams(hash.replace(/^#/, "")).get("token");
  return fromHash ?? new URLSearchParams(search).get("token") ?? "";
}

export function useLinkToken(): string {
  const location = useLocation();
  const navigate = useNavigate();
  const [token] = useState(() => readLinkToken(location.hash, location.search));

  useEffect(() => {
    const search = new URLSearchParams(location.search);
    const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
    if (!search.has("token") && !hash.has("token")) return;
    search.delete("token");
    hash.delete("token");
    const rest = search.toString();
    const restHash = hash.toString();
    navigate(
      {
        pathname: location.pathname,
        search: rest ? `?${rest}` : "",
        hash: restHash ? `#${restHash}` : "",
      },
      { replace: true },
    );
  }, [location.hash, location.pathname, location.search, navigate]);

  return token;
}
