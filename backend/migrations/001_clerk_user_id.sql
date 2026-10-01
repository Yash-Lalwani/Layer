ALTER TABLE users ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS users_clerk_user_id_key ON users (clerk_user_id);
ALTER TABLE users DROP COLUMN IF EXISTS password_hash;
