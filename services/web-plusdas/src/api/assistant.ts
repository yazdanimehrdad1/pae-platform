import type {
  AskRequest, AskResponse, AssistantSite, Conversation, ConversationRenameRequest, ConversationSummary, ConversationTurn,
  FeedbackRequest,
} from './types/assistant';
import { intelliGatewayClient } from './client';

// The AI assistant (intelli-gateway): ask about one site, and the user's saved conversations.
// Only the sites the user may access are listed or answered; a conversation is kept until its
// user deletes it.
export const assistantApi = {
  /** The sites the user may ask about (intelli-gateway's numeric site ids). */
  sites: (): Promise<AssistantSite[]> => intelliGatewayClient.get('/v1/sites'),
  ask: (siteId: number, body: AskRequest): Promise<AskResponse> =>
    intelliGatewayClient.post(`/v1/sites/${siteId}/ask`, body),
  conversations: (siteId?: number): Promise<ConversationSummary[]> =>
    intelliGatewayClient.get(siteId === undefined ? '/v1/conversations' : `/v1/conversations?site_id=${siteId}`),
  conversation: (conversationId: string): Promise<Conversation> =>
    intelliGatewayClient.get(`/v1/conversations/${encodeURIComponent(conversationId)}`),
  rename: (conversationId: string, body: ConversationRenameRequest): Promise<ConversationSummary> =>
    intelliGatewayClient.patch(`/v1/conversations/${encodeURIComponent(conversationId)}`, body),
  /** Permanently: every question and answer goes with it. */
  remove: (conversationId: string): Promise<void> =>
    intelliGatewayClient.delete(`/v1/conversations/${encodeURIComponent(conversationId)}`),
  setFeedback:(conversationId: string, turnId: number, body: FeedbackRequest): Promise<ConversationTurn> =>
    intelliGatewayClient.put(`/v1/conversations/${encodeURIComponent(conversationId)}/turns/${turnId}/feedback`, body),
};
