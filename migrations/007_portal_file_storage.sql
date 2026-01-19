-- OMI Global Productions - Portal File Storage in Database
-- Migration: 007_portal_file_storage.sql
-- Created: 2026-01-19
-- Description: Store file content directly in database with complete metadata

-- Add file content column to portal_files (stores binary data)
ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS file_content BYTEA;

-- Add additional metadata columns for complete file information
ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS original_filename VARCHAR(500);

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS extension VARCHAR(50);

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS checksum_md5 VARCHAR(32);

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS checksum_sha256 VARCHAR(64);

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS content_encoding VARCHAR(50);

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS width INTEGER; -- For images

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS height INTEGER; -- For images

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS duration_seconds FLOAT; -- For audio/video

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE portal_files
ADD COLUMN IF NOT EXISTS tags TEXT[]; -- Array of tags for categorization

-- Portal chat messages table for admin chat interface
CREATE TABLE IF NOT EXISTS portal_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id UUID NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES portal_users(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text' CHECK (message_type IN ('text', 'file', 'system', 'notification')),
    file_id UUID REFERENCES portal_files(id) ON DELETE SET NULL,
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,
    is_broadcast BOOLEAN DEFAULT false, -- For system-wide announcements
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portal_chat_sender ON portal_chat_messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_portal_chat_recipient ON portal_chat_messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_portal_chat_created ON portal_chat_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_portal_chat_unread ON portal_chat_messages(recipient_id, is_read) WHERE is_read = false;

COMMENT ON COLUMN portal_files.file_content IS 'Binary content of the file stored directly in database';
COMMENT ON COLUMN portal_files.original_filename IS 'Original filename as uploaded by user';
COMMENT ON COLUMN portal_files.extension IS 'File extension without dot (e.g., pdf, jpg)';
COMMENT ON COLUMN portal_files.checksum_md5 IS 'MD5 hash of file content for integrity verification';
COMMENT ON COLUMN portal_files.checksum_sha256 IS 'SHA256 hash of file content for integrity verification';
COMMENT ON TABLE portal_chat_messages IS 'Chat messages between portal administrators';
