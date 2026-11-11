<!-- This document is a starting point, not legal advice — have counsel review it for your product.
Values come from shared/brand.toml via scripts/gen_brand.py.
Placeholders: {{company_name}}, {{service_name}}, {{website_url}},
{{support_email}}, {{effective_date}}, {{jurisdiction_state}},
{{jurisdiction_country}}, {{arbitration_venue}}, {{minimum_age}}.
-->

# Privacy Policy

Last Updated: {{effective_date}}

## Definitions

- **"Company"** (also "**we**", "**us**", or "**our**") refers to {{company_name}}.
- **"Service"** refers to {{service_name}}, accessible at {{website_url}}, including all related websites, applications, APIs, features, and content.
- **"User"** (also "**you**" or "**your**") refers to any individual or entity that accesses or uses the Service.
- **"Personal Information"** means information that identifies, relates to, or could reasonably be linked to an individual.
- **"Organization"** means a workspace or tenant account on the Service.

This Privacy Policy describes how the Company collects, uses, discloses, and protects information when you use the Service. By using the Service, you acknowledge this Policy. Our [Terms of Service](/terms) govern use of the Service and are incorporated by reference where applicable.

## 1. Scope and Roles

This Policy covers:

- **Account and Service data** about Users and Organizations (customers and visitors)
- **Operational data** generated when you use the Service (logs, billing metadata, Credits usage)

If you wish to exercise applicable privacy rights, submit a request at [/privacy/request](/privacy/request) or contact us at {{support_email}}. We may need to verify your identity before processing your request.

When you submit personal data of third parties to the Service, **you** are responsible for ensuring your use is lawful. The Company provides tools under the Terms; you determine the purpose of your processing.

## 2. Information We Collect

### a. Information You Provide Directly

- **Account information:** first and last name, email address, and password (stored only in hashed form; we never store your plaintext password)
- **Organization information:** Organization names and slugs, optional claimed email domains, membership roles, and email addresses of people you invite
- **Consent and preference records:** the date you accepted our Terms of Service; marketing email opt-in or opt-out status
- **Uploaded files:** profile images you upload, along with file type, size, and ownership metadata. Files are stored using the Service's configured object storage provider (local storage or an S3-compatible provider). Profile images are served by an unguessable link without requiring sign-in; anyone with that link can view the image.
- **Feature inputs:** details you submit when using features of the Service (for example, prompts, uploads, or other parameters)
- **Payment information:** if you purchase a subscription or Credits, payment details are collected and processed by our payment processor (Stripe). We do not store full payment card numbers; we retain subscription and purchase metadata such as plan, status, customer and subscription identifiers, and billing period
- **Communications:** information you send in support requests, emails, or other correspondence
- **User Content:** prompts, feedback, or other content you submit to optional AI or other features

### b. Information Collected Automatically

- IP address, browser type and version, device type, and operating system
- Approximate location derived from IP address (where processed by our infrastructure or security tooling)
- Log data, including server logs, error logs, request paths, timestamps, and diagnostic context
- Pages visited and features used within the Service (for security, metering, and product operation)
- **Product usage records (signed-in accounts only):** when you are signed in, we record which features your account uses — for example, that an organization was created, an invitation was sent, a checkout was started, or an AI generation completed — together with the time and limited non-content attributes such as a plan name, a role, or a credit amount. These records are tied to your account identifier. They never contain what you type or create (prompts, messages, names, email addresses), and we do not create them for visitors who are not signed in. See Section 4 for how to turn this off
- Authentication and session signals (see Cookies)
- Credits ledger entries and usage attribution within an Organization
- Rate-limiting and abuse-prevention signals

When errors occur, we may temporarily store request context (such as IP address, user agent, path, and error details) to diagnose and resolve issues. Such diagnostic context is retained for a limited period (typically up to seven days) unless needed longer for security or legal reasons.

### c. Information from Third Parties

- **Payment processor:** Stripe sends subscription, invoice, and billing-status events
- **Email provider:** delivery, bounce, complaint, and unsubscribe events for transactional and (if opted in) marketing email
- **Error monitoring (if enabled):** tools such as Sentry may receive technical error data; we configure such tools to limit unnecessary personal data where practicable
- **AI providers (if you use AI features):** providers such as Google (Gemini), OpenAI, or Anthropic may process prompts you submit to those features

## 3. How We Use Information

We use the information we collect to:

- Provide, operate, maintain, and secure the Service
- Authenticate Users, manage Organizations, and enforce access controls
- Meter usage, reserve/capture/release Credits, and enforce plan limits
- Process transactions and send invoices, receipts, and billing notices
- Send administrative communications (security alerts, service updates, verification and password-reset emails, Organization invitations)
- Send marketing communications **only** where you have opted in; you may unsubscribe at any time
- Respond to inquiries and provide customer support
- Monitor, investigate, and prevent fraud, abuse, scraping, and unauthorized activity
- Improve and personalize the Service and develop new features
- Comply with legal obligations and enforce our Terms of Service
- Protect the rights, safety, and property of the Company, Users, and the public
- For any other purpose disclosed to you at the time of collection or with your consent

## 4. Cookies and Tracking Technologies

We use the following technologies:

- **Strictly necessary cookies:** we set an authentication cookie (a refresh token) to keep you signed in securely. It is an httpOnly cookie inaccessible to scripts. These cookies are required for the Service to operate and do not require consent.
- **Local storage:** we may store interface preferences (such as your most recently selected Organization) in your browser's local storage. We also store your cookie-consent choice itself in local storage so we do not ask again on every visit; if you are signed in, each consent decision is additionally recorded to your account so we can demonstrate and honor it.
- **Analytics (opt-in only):** with your prior consent, we use Google Analytics 4 (Google LLC) to understand aggregate site usage. Analytics loads only after you allow the Analytics category on our consent banner; if you reject it or make no choice, no analytics code loads and no data is sent. We configure analytics to receive page routes and feature-usage events (the name of an action, such as "invitation sent", with non-content attributes such as a role or plan name) — user inputs, URL query parameters, and resource identifiers are stripped before anything is sent. If you are signed in, a one-way hashed account identifier is included so that visits from your devices can be counted as one user; your name and email address are never sent. You may change or withdraw your choice at any time via the "Cookie settings" link in the footer or on your profile page; after withdrawal, analytics will not load on subsequent page loads.
- **First-party product usage records (no cookies):** the product usage records described in Section 2(b) are created on our own servers from requests you make while signed in. They do not store or read anything on your device, are not shared with Google or any advertising or analytics provider, and therefore do not depend on the consent banner. We rely on our legitimate interest in understanding how the Service is used. You can object at any time: turn off "usage analytics" on your profile page and we stop creating these records for your account — on every device — and also stop sending analytics to Google for your account, regardless of your cookie choice. Turning it off does not delete records already created; to have those erased, submit a deletion request as described in Section 12.

We do not use third-party advertising cookies. If we introduce additional analytics or marketing technologies in the future, we will update this Policy and, where required, obtain prior opt-in consent through the same consent mechanism before loading them.

You can configure your browser to refuse or delete cookies. If you refuse the strictly necessary authentication cookie, you will not be able to remain signed in and some features will not function.

## 5. Third-Party Services

We rely on the following categories of third-party services:

- **Payments:** Stripe (subscription billing, Credit pack purchases, and payment processing)
- **Email delivery:** a transactional email provider (for account, invitation, and billing emails, and — only if you opt in — marketing email). In production this may be Resend or a similar provider; in development, email may be captured by a local mail testing tool
- **Infrastructure and hosting:** cloud infrastructure providers that host the Service, databases, cache, and object storage
- **Error monitoring:** optional tools such as Sentry for application error tracking
- **Analytics:** Google Analytics (Google LLC), loaded only after opt-in consent as described in Section 4
- **AI providers:** optional providers (for example Gemini, OpenAI, Anthropic) when AI features are enabled and used

These third-party services have their own privacy policies governing their use of information. We are not responsible for the privacy practices of third-party services. We encourage you to review the privacy policies of any third-party services you interact with through our Service.

## 6. Data Sharing and Disclosure

We may share information in the following circumstances:

- **Service providers:** with vendors that perform services on our behalf (payment processing, email delivery, hosting, monitoring, AI processing), subject to contractual obligations appropriate to the service
- **Within your Organizations:** your name, email address, and role are visible to other members of Organizations you belong to; owners and administrators may see usage and billing metadata for the Organization
- **Legal compliance:** when required by law, regulation, legal process, or governmental request
- **Protection of rights:** to enforce our Terms, or to protect the rights, privacy, safety, or property of the Company, our Users, data subjects, or the public
- **Business transfers:** in connection with any merger, acquisition, financing, reorganization, sale of assets, or bankruptcy
- **With consent:** when you have given explicit consent
- **Aggregated or anonymized data:** we may share aggregated or de-identified information that cannot reasonably be used to identify you

**We do not sell Personal Information** as "sale" is commonly defined under the CCPA/CPRA. We do not share Personal Information for cross-context behavioral advertising. If that changes, we will update this Policy and provide required opt-out mechanisms.

## 7. AI Processing

Certain features of the Service may use artificial intelligence. Content you submit to those features may be transmitted to and processed by third-party AI providers (such as Google Gemini, OpenAI, or Anthropic, depending on configuration) to generate responses.

We do not control how third-party AI providers use data beyond our agreements with them; their privacy policies apply to their processing. Do not submit sensitive Personal Information (health data, financial account numbers, government identifiers, or similar) to AI-powered features unless necessary and lawful. AI-related inputs and outputs may be retained to provide, secure, and improve the Service and to maintain audit records (including Credits metering).

## 8. Data Retention

We retain Personal Information for as long as necessary to provide the Service and fulfill the purposes described in this Privacy Policy, including:

- **Uploaded profile images:** replacing or removing an uploaded profile image removes its file record and initiates deletion from the configured storage provider. Storage failures can delay object deletion; copies already downloaded or cached by others may remain.
- **Account data:** for the life of the account and a reasonable period thereafter
- **Billing and transaction records:** as required for accounting, tax, dispute resolution, and legal compliance
- **Credits ledgers:** as needed for metering integrity and audit
- **Marketing preferences and consent records:** as needed to demonstrate compliance
- **Product usage records:** 24 months from the date of each record, after which they are deleted automatically; they are also deleted when your account is deleted
- **Privacy-request records:** raw request details are removed after approximately 90 days; status, identifier fingerprints, and processing metadata are retained longer for audit purposes
- **Error and security logs:** typically for a short period (for example, up to seven days for detailed request context), longer if needed for investigations

After account deletion, we may retain certain information as required by law, to resolve disputes, enforce agreements, prevent fraud, or for legitimate business purposes. We may retain aggregated or anonymized data indefinitely. Organization-owned data may persist after an individual member leaves until the Organization is deleted or as otherwise required.

## 9. Data Security

We implement commercially reasonable technical and organizational security measures designed to protect Personal Information, including password hashing, encrypted connections (TLS), access controls, and network isolation in our hosting environment.

However, no method of transmission over the Internet or method of electronic storage is 100% secure, and we cannot guarantee absolute security. We are not responsible for unauthorized access that occurs despite our reasonable security measures. You are responsible for maintaining the security of your account credentials and for configuring Organization access appropriately.

If we become aware of a security incident that requires notification under applicable law, we will notify affected parties as required.

## 10. Children's Privacy

The Service is not directed to individuals under the age of **{{minimum_age}}**. We do not knowingly collect Personal Information from children under {{minimum_age}}. If we become aware that we have collected Personal Information from a child under {{minimum_age}}, we will take steps to delete such information promptly. If you believe a child has provided us with Personal Information, please contact us at {{support_email}}.

You must not use the Service to target or exploit minors.

## 11. International Data Transfers

Your information may be transferred to and processed in countries other than your country of residence, including the United States. These countries may have data protection laws that differ from those in your jurisdiction.

Where we transfer Personal Information out of the European Economic Area or the United Kingdom, we rely on appropriate safeguards such as adequacy decisions or Standard Contractual Clauses (SCCs), where required. We will take reasonable steps to ensure your information is treated securely and in accordance with this Privacy Policy.

## 12. Your Privacy Rights

Depending on your jurisdiction, you may have some or all of the following rights regarding your Personal Information:

- **Access:** request a copy of Personal Information we hold about you
- **Correction:** request correction of inaccurate information
- **Deletion:** request deletion of your Personal Information
- **Portability:** request transfer of information in a machine-readable format
- **Objection / restriction:** object to or request restriction of certain processing. You can object to product usage analytics directly, at any time, using the "usage analytics" setting on your profile page (see Section 4)
- **Withdraw consent:** where processing is based on consent (for example, marketing email), withdraw consent at any time without affecting prior lawful processing

To exercise any of these rights, submit a request at [/privacy/request](/privacy/request) or contact us at {{support_email}}. We may need to verify your identity before processing your request. We reserve the right to charge a reasonable fee for manifestly unfounded or excessive requests, where permitted by law. We may deny requests that are exempt, or limit responses where disclosure would adversely affect the rights of others or our trade secrets and security.

**Marketing.** You can unsubscribe from marketing emails via the link in those emails or by updating your profile preferences. Transactional emails (security, billing, invitations) are not marketing and may continue as needed to operate the Service.

## 13. California Privacy Rights (CCPA/CPRA)

If you are a California resident, you may have additional rights under the California Consumer Privacy Act as amended by the CPRA, including the right to know, the right to delete, the right to correct, the right to opt out of sale or sharing, the right to limit use of sensitive personal information (where applicable), and the right to non-discrimination.

**Categories of Personal Information.** Depending on how you use the Service, we may collect identifiers (name, email, IP address); commercial information (plan and purchase history); internet or electronic activity (usage logs); and professional information (Organization membership). We do not profile you for advertising.

**Sources.** You; your Organization administrators; automatic collection; and payment and email providers.

**Business purposes.** As described in Section 3 (providing the Service, security, billing, compliance, and improvement).

**We do not sell Personal Information** as defined by the CCPA, and we do not share it for cross-context behavioral advertising. To exercise your California privacy rights, contact us at {{support_email}}. You may also designate an authorized agent subject to verification requirements.

## 14. European Privacy Rights (GDPR)

If you are a resident of the European Economic Area or the United Kingdom, you may have additional rights under the GDPR (or UK GDPR), including access, rectification, erasure, restriction, portability, objection, and the right to withdraw consent where processing is based on consent. You also have the right to lodge a complaint with a supervisory authority.

**Lawful bases** for processing typically include:

- **Contract performance:** creating and managing your account, providing the Service you request, billing
- **Legitimate interests:** securing the Service, preventing fraud and abuse, improving features, enforcing Terms, and first-party product usage records for signed-in accounts that do not rely on cookies or similar technologies (you may object at any time from your profile page)
- **Consent:** marketing emails; Google Analytics and any other non-essential cookies or similar technologies
- **Legal obligation:** tax, accounting, and responding to lawful requests

Analytics and marketing cookies are used only after prior opt-in consent, which you may withdraw at any time via the consent mechanism we provide, without affecting the lawfulness of processing before withdrawal.

To exercise your GDPR rights, contact us at {{support_email}}.

## 15. Do Not Track

Some browsers transmit "Do Not Track" (DNT) signals. The Service does not currently respond to DNT signals. Third parties that collect data through the Service (if any) may also not respond to DNT signals.

## 16. Changes to This Privacy Policy

We may update this Privacy Policy at any time. Changes are effective when posted on this page. Your continued use of the Service after any changes constitutes acceptance of the updated Privacy Policy. We encourage you to review this Privacy Policy periodically. For material changes, we may provide additional notice (for example, by email or in-product notice).

## 17. Contact

If you have any questions about this Privacy Policy, please contact us at {{support_email}}.
