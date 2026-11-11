import terms from "./TERMS_OF_SERVICE.md?raw";
import LegalPage from "./LegalPage";

export default function TermsPage() {
  return <LegalPage markdown={terms} data-testid="terms-page" />;
}
