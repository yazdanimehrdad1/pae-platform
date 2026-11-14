// React Query keys of the assistant page, in one place.
export const ASSISTANT_SITES_QUERY_KEY = ["assistant", "sites"] as const;
export const conversationsQueryKey = (siteId: number | null) => ["assistant", "conversations", siteId] as const;
export const conversationQueryKey = (conversationId: string) => ["assistant", "conversation", conversationId] as const;
