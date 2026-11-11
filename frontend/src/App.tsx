import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import RequireFeature from "./components/RequireFeature";
import { CookieConsent } from "./features/consent";
import { ROUTES, ROUTE_PATTERNS } from "./shared/lib/routes";
import { trackPageView } from "./shared/lib/track";
import FullScreenSpinner from "./shared/ui/FullScreenSpinner";

const AdminRevenuePage = lazy(() => import("./features/admin/AdminRevenuePage"));
const AdminOrgEntitlementsPage = lazy(() => import("./features/admin/AdminOrgEntitlementsPage"));
const AdminAuditPage = lazy(() => import("./features/admin/AdminAuditPage"));
const AdminCompliancePage = lazy(() => import("./features/admin/AdminCompliancePage"));
const AdminCreditsPage = lazy(() => import("./features/admin/AdminCreditsPage"));
const AdminCustomersPage = lazy(() => import("./features/admin/AdminCustomersPage"));
const AdminErrorLookupPage = lazy(() => import("./features/admin/AdminErrorLookupPage"));
const AdminCommunityPage = lazy(() => import("./features/admin/AdminCommunityPage"));
const AdminFlagsPage = lazy(() => import("./features/admin/AdminFlagsPage"));
const AdminGenerationsPage = lazy(() => import("./features/admin/AdminGenerationsPage"));
const AdminBlogEditorPage = lazy(() => import("./features/blog/components/AdminBlogEditorPage"));
const AdminBlogListPage = lazy(() => import("./features/blog/components/AdminBlogListPage"));
const AdminInvitationsPage = lazy(() => import("./features/admin/AdminInvitationsPage"));
const AdminLayout = lazy(() => import("./features/admin/AdminLayout"));
const AdminOrgsPage = lazy(() => import("./features/admin/AdminOrgsPage"));
const AdminOverviewPage = lazy(() => import("./features/admin/AdminOverviewPage"));
const AdminPrivacyRequestsPage = lazy(() => import("./features/admin/AdminPrivacyRequestsPage"));
const AdminUsersPage = lazy(() => import("./features/admin/AdminUsersPage"));
const ApiDocsPage = lazy(() => import("./features/api-docs/components/ApiDocsPage"));
const ApiKeysPage = lazy(() => import("./features/api-keys/components/ApiKeysPage"));
const BillingPage = lazy(() => import("./features/billing/components/BillingPage"));
const CommunityPage = lazy(() => import("./features/community/components/CommunityPage"));
const CommunityMemberPage = lazy(() => import("./features/community/components/MemberProfilePage"));
const CommunityMessagesPage = lazy(() => import("./features/community/components/MessagesPage"));
const CommunityUpgradePage = lazy(() => import("./features/community/components/UpgradePage"));
const BlogArticlePage = lazy(() => import("./features/blog/components/BlogArticlePage"));
const BlogListPage = lazy(() => import("./features/blog/components/BlogListPage"));
const BlogPreviewPage = lazy(() => import("./features/blog/components/BlogPreviewPage"));
const DashboardPage = lazy(() => import("./features/dashboard/components/DashboardPage"));
const DesignSystemPage = lazy(() => import("./features/design-system/DesignSystemPage"));
const ForgotPasswordPage = lazy(() => import("./features/auth/components/ForgotPasswordPage"));
const HomePage = lazy(() => import("./features/home/HomePage"));
const LoginPage = lazy(() => import("./features/auth/components/LoginPage"));
const NotFoundPage = lazy(() => import("./features/home/NotFoundPage"));
const PricingPage = lazy(() => import("./features/billing/components/PricingPage"));
const PrivacyPage = lazy(() => import("./features/legal/PrivacyPage"));
const PrivacyRequestPage = lazy(() => import("./features/legal/PrivacyRequestPage"));
const ProfilePage = lazy(() => import("./features/auth/components/ProfilePage"));
const RegisterPage = lazy(() => import("./features/auth/components/RegisterPage"));
const ResetPasswordPage = lazy(() => import("./features/auth/components/ResetPasswordPage"));
const SaasFeaturesPage = lazy(() => import("./features/saas-features/components/SaasFeaturesPage"));
const TermsPage = lazy(() => import("./features/legal/TermsPage"));
const VerifyEmailPage = lazy(() => import("./features/auth/components/VerifyEmailPage"));
const AcceptInvitePage = lazy(() => import("./features/organizations/components/AcceptInvitePage"));
const CreateOrgPage = lazy(() => import("./features/organizations/components/CreateOrgPage"));
const MembersPage = lazy(() => import("./features/organizations/components/MembersPage"));
const SettingsPage = lazy(() => import("./features/organizations/components/SettingsPage"));

// SPA page_views are fired from route changes only (gtag config disables the
// automatic one); analytics.ts strips query strings and resource ids.
// GA-only by design: the first-party activity_events table holds feature and
// business events, never page views (see docs/analytics.md).
function PageViewTracker() {
  const location = useLocation();
  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <PageViewTracker />
      <CookieConsent />
      <Suspense fallback={<FullScreenSpinner />}>
        <Routes>
          <Route path={ROUTES.home} element={<HomePage />} />
          <Route path={ROUTES.pricing} element={<PricingPage />} />
          <Route path={ROUTES.blog.list} element={<BlogListPage />} />
          {/* Must precede /blog/:slug so "preview" isn't matched as a slug. */}
          <Route path={ROUTES.blog.preview} element={<BlogPreviewPage />} />
          <Route path={ROUTE_PATTERNS.blog.post} element={<BlogArticlePage />} />
          <Route path={ROUTES.docs} element={<ApiDocsPage />} />
          <Route path={ROUTES.auth.login} element={<LoginPage />} />
          <Route path={ROUTES.auth.register} element={<RegisterPage />} />
          <Route path={ROUTES.auth.forgotPassword} element={<ForgotPasswordPage />} />
          <Route path={ROUTES.auth.resetPassword} element={<ResetPasswordPage />} />
          <Route path={ROUTES.auth.verifyEmail} element={<VerifyEmailPage />} />
          <Route path={ROUTES.legal.terms} element={<TermsPage />} />
          <Route path={ROUTES.legal.privacy} element={<PrivacyPage />} />
          <Route path={ROUTES.legal.privacyRequest} element={<PrivacyRequestPage />} />
          <Route element={<RequireAuth />}>
            <Route path={ROUTES.organizations.create} element={<CreateOrgPage />} />
            <Route path={ROUTES.organizations.acceptInvite} element={<AcceptInvitePage />} />
            <Route path={ROUTES.admin.overview} element={<AdminLayout />}>
              <Route index element={<AdminOverviewPage />} />
              <Route path={ROUTES.admin.revenue} element={<AdminRevenuePage />} />
              <Route
                path={ROUTE_PATTERNS.admin.orgEntitlements}
                element={<AdminOrgEntitlementsPage />}
              />
              <Route path={ROUTES.admin.customers} element={<AdminCustomersPage />} />
              <Route path={ROUTES.admin.orgs} element={<AdminOrgsPage />} />
              <Route path={ROUTES.admin.users} element={<AdminUsersPage />} />
              <Route path={ROUTES.admin.credits} element={<AdminCreditsPage />} />
              <Route path={ROUTES.admin.generations} element={<AdminGenerationsPage />} />
              <Route path={ROUTES.admin.invitations} element={<AdminInvitationsPage />} />
              <Route path={ROUTES.admin.audit} element={<AdminAuditPage />} />
              <Route path={ROUTES.admin.privacyRequests} element={<AdminPrivacyRequestsPage />} />
              <Route path={ROUTES.admin.blog} element={<AdminBlogListPage />} />
              <Route path={ROUTES.admin.newBlogPost} element={<AdminBlogEditorPage />} />
              <Route path={ROUTE_PATTERNS.admin.blogPost} element={<AdminBlogEditorPage />} />
              <Route path={ROUTES.admin.compliance} element={<AdminCompliancePage />} />
              <Route path={ROUTES.admin.flags} element={<AdminFlagsPage />} />
              <Route path={ROUTES.admin.community} element={<AdminCommunityPage />} />
              <Route path={ROUTES.admin.errors} element={<AdminErrorLookupPage />} />
            </Route>
            <Route element={<AppLayout />}>
              <Route path={ROUTES.dashboard} element={<DashboardPage />} />
              <Route path={ROUTES.credits} element={<Navigate to={ROUTES.billing} replace />} />
              <Route path={ROUTES.members} element={<MembersPage />} />
              <Route path={ROUTES.billing} element={<BillingPage />} />
              <Route path={ROUTES.saasFeatures} element={<SaasFeaturesPage />} />
              <Route path={ROUTES.settings} element={<SettingsPage />} />
              <Route path={ROUTES.apiKeys} element={<ApiKeysPage />} />
              <Route path={ROUTES.profile} element={<ProfilePage />} />
              <Route element={<RequireFeature flag="community" />}>
                <Route path={ROUTES.community.list} element={<CommunityPage />} />
                <Route path={ROUTE_PATTERNS.community.member} element={<CommunityMemberPage />} />
                <Route path={ROUTES.community.messages} element={<CommunityMessagesPage />} />
                <Route
                  path={ROUTE_PATTERNS.community.conversation}
                  element={<CommunityMessagesPage />}
                />
                <Route path={ROUTES.community.upgrade} element={<CommunityUpgradePage />} />
              </Route>
            </Route>
          </Route>
          {/* Living design-system reference (DESIGN.md) — development builds only. */}
          {import.meta.env.DEV && (
            <Route path={ROUTES.designSystem} element={<DesignSystemPage />} />
          )}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
