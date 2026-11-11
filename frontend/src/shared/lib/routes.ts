// Typed registry for in-app URLs and React Router patterns:
// never write a route path literal outside this file.
// Builders preserve caller-provided segments; encode at the call site when needed.
export const ROUTES = {
  home: "/",
  pricing: "/pricing",
  docs: "/docs",
  dashboard: "/dashboard",
  credits: "/credits",
  members: "/members",
  billing: "/billing",
  saasFeatures: "/saas-features",
  // Living design-system reference; registered in development builds only.
  designSystem: "/design-system",
  settings: "/settings",
  apiKeys: "/api-keys",
  profile: "/profile",
  auth: {
    login: "/login",
    register: "/register",
    forgotPassword: "/forgot-password",
    resetPassword: "/reset-password",
    verifyEmail: "/verify-email",
  },
  legal: {
    terms: "/terms",
    privacy: "/privacy",
    privacyRequest: "/privacy/request",
  },
  organizations: {
    create: "/orgs/new",
    acceptInvite: "/invitations/accept",
  },
  blog: {
    list: "/blog",
    preview: "/blog/preview",
    post: (slug: string) => `/blog/${slug}`,
  },
  community: {
    list: "/community",
    member: (handle: string) => `/community/members/${handle}`,
    messages: "/community/messages",
    conversation: (id: string) => `/community/messages/${id}`,
    upgrade: "/community/upgrade",
  },
  admin: {
    overview: "/admin",
    revenue: "/admin/revenue",
    orgEntitlements: (orgId: string) => `/admin/orgs/${orgId}/entitlements`,
    customers: "/admin/customers",
    orgs: "/admin/orgs",
    users: "/admin/users",
    credits: "/admin/credits",
    generations: "/admin/generations",
    invitations: "/admin/invitations",
    audit: "/admin/audit",
    privacyRequests: "/admin/privacy-requests",
    blog: "/admin/blog",
    newBlogPost: "/admin/blog/new",
    blogPost: (id: string) => `/admin/blog/${id}`,
    compliance: "/admin/compliance",
    flags: "/admin/flags",
    community: "/admin/community",
    errors: "/admin/errors",
  },
} as const;

// Parameterized patterns belong only in the route table, never in navigation.
export const ROUTE_PATTERNS = {
  blog: {
    post: "/blog/:slug",
  },
  community: {
    member: "/community/members/:handle",
    conversation: "/community/messages/:conversationId",
  },
  admin: {
    blogPost: "/admin/blog/:id",
    orgEntitlements: "/admin/orgs/:orgId/entitlements",
  },
} as const;
