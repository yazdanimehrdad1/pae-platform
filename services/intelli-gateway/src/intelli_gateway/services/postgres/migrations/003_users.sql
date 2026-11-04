-- Migration: 003_users
-- PlusDAS user accounts and their login sessions. Accounts are created by an admin
-- (`make create-user`); there is no self-signup. A session row holds only the SHA-256 of the
-- cookie's random token, never the token itself.

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    -- The sign-in name. Stored lower-case: logins are case-insensitive.
    email TEXT NOT NULL UNIQUE CHECK (email = lower(email) AND length(email) BETWEEN 3 AND 254),
    display_name TEXT NOT NULL,
    -- scrypt$<n>$<r>$<p>$<salt b64>$<hash b64> (hashlib.scrypt, a per-user salt)
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('engineer', 'admin', 'monitor')),
    disabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE user_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    -- Sliding: pushed forward when the session is used (at most once a minute).
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX user_sessions_user_id_idx ON user_sessions (user_id);
CREATE INDEX user_sessions_expires_at_idx ON user_sessions (expires_at);

COMMENT ON TABLE users IS 'PlusDAS user accounts (individual, admin-created); role engineer | admin | monitor';
COMMENT ON TABLE user_sessions IS 'Login sessions: SHA-256 of the cookie token, sliding expiry; deleted on logout and when the user is disabled';
