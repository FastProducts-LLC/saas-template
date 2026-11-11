// Public API of the consent feature. Other code must import from here only.

export { default as CookieConsent } from "./components/CookieConsent";
export { consentAllows, openCookieSettings } from "./model/store";
