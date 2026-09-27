// Auth mock: accepts any non-empty email and password. backend-ot has no auth yet
// (docs/backend-gaps.md, "Login / auth").
import type { User, UserRole } from '@/shared/contexts/auth';

// Resolves with the signed-in user, or null when a field is empty, after a fake 1 s round trip.
export async function mockLogin(email: string, password: string, role: UserRole): Promise<User | null> {
  await new Promise(resolve => setTimeout(resolve, 1000));
  if (!email || !password) return null;
  return {
    id: '1',
    email,
    name: email.split('@')[0],
    role
  };
}
