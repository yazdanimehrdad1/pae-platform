import type { components } from '@contracts/intelli-gateway';

type Schemas = components['schemas'];

// Wire types: generated from intelli-gateway's contract (it owns PlusDAS users), never hand-written.
export type MeResponse = Schemas['MeResponse'];
export type LoginRequest = Schemas['LoginRequest'];
export type Preference = Schemas['Preference'];
export type SavedTrend = Schemas['SavedTrend'];
export type TrendDefinition = Schemas['TrendDefinition'];
export type SavedNote = Schemas['Note'];
export type NoteCreateRequest = Schemas['NoteCreateRequest'];
export type PasswordChangeRequest = Schemas['PasswordChangeRequest'];
export type UserAccount = Schemas['UserResponse'];
export type UserCreateRequest = Schemas['UserCreateRequest'];
export type UserUpdateRequest = Schemas['UserUpdateRequest'];
export type UserRole = UserAccount['role'];
