-- OMI Global Productions - Admin Portal Users Schema
-- Migration: 006_portal_users.sql
-- Created: 2026-01-19
-- Description: Tables for admin portal users and file management

-- Admin users table for portal authentication
CREATE TABLE IF NOT EXISTS portal_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'admin' CHECK (role IN ('admin', 'superadmin', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for login lookups
CREATE INDEX IF NOT EXISTS idx_portal_users_username ON portal_users(username);
CREATE INDEX IF NOT EXISTS idx_portal_users_email ON portal_users(email);

-- Admin sessions for token management
CREATE TABLE IF NOT EXISTS portal_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portal_sessions_token ON portal_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_user_id ON portal_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_expires_at ON portal_sessions(expires_at);

-- Portal files table for file explorer
CREATE TABLE IF NOT EXISTS portal_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(500) NOT NULL,
    path VARCHAR(2048) NOT NULL,
    mime_type VARCHAR(255),
    size_bytes BIGINT DEFAULT 0,
    is_folder BOOLEAN DEFAULT false,
    parent_id UUID REFERENCES portal_files(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES portal_users(id),
    storage_key VARCHAR(2048), -- For S3 or local storage path
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portal_files_path ON portal_files(path);
CREATE INDEX IF NOT EXISTS idx_portal_files_parent_id ON portal_files(parent_id);
CREATE INDEX IF NOT EXISTS idx_portal_files_name ON portal_files(name);

-- Create root folder for uploads
INSERT INTO portal_files (id, name, path, is_folder, parent_id)
VALUES ('00000000-0000-0000-0000-000000000001', 'uploads', '/uploads', true, NULL)
ON CONFLICT DO NOTHING;

-- Insert default admin user (password: admin123 - should be changed immediately)
-- Password hash is bcrypt for 'admin123'
INSERT INTO portal_users (username, email, password_hash, full_name, role)
VALUES (
    'admin',
    'vijay@omiproductions.com',
    '$2b$12$4o.7Jm.DUZ7VxqhUfUZ4HOqgJgNtzjieuQ57FcWcIIbjbjyw2pExO',
    'OMI Administrator',
    'superadmin'
)
ON CONFLICT (username) DO NOTHING;

COMMENT ON TABLE portal_users IS 'Admin portal user accounts';
COMMENT ON TABLE portal_sessions IS 'Active sessions for portal authentication';
COMMENT ON TABLE portal_files IS 'File explorer structure for uploaded assets';
