import type { components } from '@contracts/intelli-gateway';

type Schemas = components['schemas'];

// Wire types: generated from intelli-gateway's contract, never hand-written.
export type AssistantSite = Schemas['SiteResponse'];
export type AskRequest = Schemas['AskRequest'];
export type AskResponse = Schemas['AskResponse'];
export type ConversationSummary = Schemas['ConversationSummaryResponse'];
export type Conversation = Schemas['ConversationResponse'];
export type ConversationTurn = Schemas['TurnResponse'];
export type ConversationRenameRequest = Schemas['ConversationRenameRequest'];
export type FeedbackRequest = Schemas['FeedbackRequest'];
export type AnswerRating = NonNullable<FeedbackRequest['rating']>;
