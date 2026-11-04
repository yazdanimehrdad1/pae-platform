import type {
  LoginRequest, MeResponse, NoteCreateRequest, PasswordChangeRequest, Preference, SavedNote, SavedTrend,
  TrendDefinition, UserAccount, UserCreateRequest, UserUpdateRequest,
} from './types/me';
import { intelliGatewayClient } from './client';

// The logged-in user and their own data, kept by intelli-gateway. The session is an HttpOnly
// cookie the browser sends by itself (same origin): no token ever passes through this code.
export const authApi = {
  login: (body: LoginRequest): Promise<MeResponse> => intelliGatewayClient.post('/v1/auth/login', body),
  logout: (): Promise<void> => intelliGatewayClient.action('/v1/auth/logout', 'POST'),
  /** The logged-in user; rejects with status 401 when there is no valid session. */
  me: (): Promise<MeResponse> => intelliGatewayClient.get('/v1/me'),
  /** Needs the current password; the user's other sessions end, this one stays. */
  changePassword: (body: PasswordChangeRequest): Promise<void> =>
    intelliGatewayClient.putNoContent('/v1/me/password', body),
};

const preferencePath = (key: string) => `/v1/me/preferences/${encodeURIComponent(key)}`;

export const meApi = {
  listPreferences: (): Promise<Preference[]> => intelliGatewayClient.get('/v1/me/preferences'),
  putPreference: (key: string, value: unknown): Promise<Preference> =>
    intelliGatewayClient.put(preferencePath(key), { value }),
  deletePreference: (key: string): Promise<void> => intelliGatewayClient.delete(preferencePath(key)),

  listTrends: (): Promise<SavedTrend[]> => intelliGatewayClient.get('/v1/me/trends'),
  createTrend: (trend: TrendDefinition): Promise<SavedTrend> => intelliGatewayClient.post('/v1/me/trends', trend),
  updateTrend: (trendId: number, trend: TrendDefinition): Promise<SavedTrend> =>
    intelliGatewayClient.put(`/v1/me/trends/${trendId}`, trend),
  deleteTrend: (trendId: number): Promise<void> => intelliGatewayClient.delete(`/v1/me/trends/${trendId}`),
  reorderTrends: (trendIds: number[]): Promise<SavedTrend[]> =>
    intelliGatewayClient.put('/v1/me/trends/order', { trend_ids: trendIds }),

  listNotes: (): Promise<SavedNote[]> => intelliGatewayClient.get('/v1/me/notes'),
  createNote: (note: NoteCreateRequest): Promise<SavedNote> => intelliGatewayClient.post('/v1/me/notes', note),
  updateNote: (noteId: number, content: string): Promise<SavedNote> =>
    intelliGatewayClient.put(`/v1/me/notes/${noteId}`, { content }),
  deleteNote: (noteId: number): Promise<void> => intelliGatewayClient.delete(`/v1/me/notes/${noteId}`),
};

// Account management, admins only (intelli-gateway answers 403 to anyone else).
export const usersApi = {
  list: (): Promise<UserAccount[]> => intelliGatewayClient.get('/v1/users'),
  create: (body: UserCreateRequest): Promise<UserAccount> => intelliGatewayClient.post('/v1/users', body),
  update: (userId: number, body: UserUpdateRequest): Promise<UserAccount> =>
    intelliGatewayClient.patch(`/v1/users/${userId}`, body),
  resetPassword: (userId: number, password: string): Promise<void> =>
    intelliGatewayClient.putNoContent(`/v1/users/${userId}/password`, { password }),
};
