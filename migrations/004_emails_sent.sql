-- OMI Global Productions - Email Tracking Schema
-- Migration: 004_emails_sent.sql
-- Created: 2026-01-17
-- Description: Table for storing all sent emails with complete content and metadata

-- Email tracking table
-- Stores complete email content, headers, and delivery status linked to project submissions
CREATE TABLE IF NOT EXISTS emails_sent (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Link to the submission that triggered this email
    submission_id UUID REFERENCES project_submissions(id) ON DELETE SET NULL,
    
    -- Email envelope
    from_email VARCHAR(255) NOT NULL,
    from_name VARCHAR(255),
    to_email VARCHAR(255) NOT NULL,
    to_name VARCHAR(255),
    reply_to VARCHAR(255),
    
    -- Email content
    subject VARCHAR(500) NOT NULL,
    body_html TEXT NOT NULL,
    body_plain TEXT NOT NULL,
    
    -- Email metadata
    email_type VARCHAR(100) NOT NULL DEFAULT 'submission_confirmation',
    
    -- SMTP response data
    message_id VARCHAR(255),
    smtp_response TEXT,
    
    -- Delivery status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_emails_sent_submission_id 
    ON emails_sent(submission_id);

CREATE INDEX IF NOT EXISTS idx_emails_sent_to_email 
    ON emails_sent(to_email);

CREATE INDEX IF NOT EXISTS idx_emails_sent_status 
    ON emails_sent(status);

CREATE INDEX IF NOT EXISTS idx_emails_sent_created_at 
    ON emails_sent(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_emails_sent_email_type 
    ON emails_sent(email_type);

-- Add comment to table
COMMENT ON TABLE emails_sent IS 'Stores all sent emails with complete content and delivery metadata';

-- Column comments for documentation
COMMENT ON COLUMN emails_sent.submission_id IS 'Foreign key to the project submission that triggered this email';
COMMENT ON COLUMN emails_sent.from_email IS 'Sender email address';
COMMENT ON COLUMN emails_sent.from_name IS 'Sender display name';
COMMENT ON COLUMN emails_sent.to_email IS 'Recipient email address';
COMMENT ON COLUMN emails_sent.to_name IS 'Recipient display name';
COMMENT ON COLUMN emails_sent.reply_to IS 'Reply-to email address';
COMMENT ON COLUMN emails_sent.subject IS 'Email subject line';
COMMENT ON COLUMN emails_sent.body_html IS 'Complete HTML body of the email';
COMMENT ON COLUMN emails_sent.body_plain IS 'Plain text version of the email body';
COMMENT ON COLUMN emails_sent.email_type IS 'Type of email: submission_confirmation, status_update, etc.';
COMMENT ON COLUMN emails_sent.message_id IS 'SMTP Message-ID header for tracking';
COMMENT ON COLUMN emails_sent.smtp_response IS 'Raw SMTP server response';
COMMENT ON COLUMN emails_sent.status IS 'Delivery status: pending, sent, failed';
COMMENT ON COLUMN emails_sent.sent_at IS 'Timestamp when email was successfully sent';
COMMENT ON COLUMN emails_sent.failed_at IS 'Timestamp when email delivery failed';
COMMENT ON COLUMN emails_sent.error_message IS 'Error message if delivery failed';
COMMENT ON COLUMN emails_sent.retry_count IS 'Number of retry attempts for failed emails';
