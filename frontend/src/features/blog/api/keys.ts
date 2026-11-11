export const blogKeys = {
  all: ["blog"] as const,
  publicList: (page: number, q: string, tag: string) =>
    ["blog", "public", "list", page, q, tag] as const,
  tags: () => ["blog", "public", "tags"] as const,
  publicPost: (slug: string) => ["blog", "public", "post", slug] as const,
  previewPost: (token: string) => ["blog", "preview", token] as const,
  adminList: (status: string, page: number) => ["blog", "admin", "list", status, page] as const,
  adminPost: (id: string) => ["blog", "admin", "post", id] as const,
  generationJob: (id: string) => ["blog", "admin", "generate", id] as const,
};
