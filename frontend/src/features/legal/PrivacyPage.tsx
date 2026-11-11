import privacy from "./PRIVACY_POLICY.md?raw";
import LegalPage from "./LegalPage";

export default function PrivacyPage() {
  return <LegalPage markdown={privacy} data-testid="privacy-page" />;
}
