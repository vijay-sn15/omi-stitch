-- OMI Global Productions - Submission Comments Schema
-- Migration: 005_submission_comments.sql
-- Created: 2026-01-17
-- Description: Table for storing comments/messages on project submissions

-- Submission comments table
-- Stores messages between users and OMI Productions administrators
CREATE TABLE IF NOT EXISTS submission_comments (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Link to the submission
    submission_id UUID NOT NULL REFERENCES project_submissions(id) ON DELETE CASCADE,
    
    -- Comment author info
    author_type VARCHAR(20) NOT NULL CHECK (author_type IN ('user', 'admin')),
    author_name VARCHAR(255) NOT NULL,
    author_email VARCHAR(255),
    
    -- Comment content
    message TEXT NOT NULL,
    
    -- Optional internal note flag (only visible to admins)
    is_internal BOOLEAN DEFAULT false,
    
    -- Read status
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_submission_comments_submission_id 
    ON submission_comments(submission_id);

CREATE INDEX IF NOT EXISTS idx_submission_comments_created_at 
    ON submission_comments(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_submission_comments_author_type 
    ON submission_comments(author_type);

-- Add comment to table
COMMENT ON TABLE submission_comments IS 'Stores comments and messages between users and admins on project submissions';

-- Column comments for documentation
COMMENT ON COLUMN submission_comments.submission_id IS 'Foreign key to the project submission';
COMMENT ON COLUMN submission_comments.author_type IS 'Type of author: user (submitter) or admin (OMI team)';
COMMENT ON COLUMN submission_comments.author_name IS 'Display name of the comment author';
COMMENT ON COLUMN submission_comments.author_email IS 'Email of the comment author';
COMMENT ON COLUMN submission_comments.message IS 'The comment/message content';
COMMENT ON COLUMN submission_comments.is_internal IS 'If true, only visible to admins (internal notes)';
COMMENT ON COLUMN submission_comments.is_read IS 'Whether the comment has been read by the recipient';

-- Add tracking_token column to project_submissions for secure access
ALTER TABLE project_submissions
ADD COLUMN IF NOT EXISTS tracking_token UUID DEFAULT gen_random_uuid();

-- Create index for tracking token lookups
CREATE INDEX IF NOT EXISTS idx_project_submissions_tracking_token 
    ON project_submissions(tracking_token);

COMMENT ON COLUMN project_submissions.tracking_token IS 'Unique token for public tracking page access (different from id for security)';
