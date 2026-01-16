-- OMI Global Productions - Add Contact Information Fields
-- Migration: 003_add_contact_fields.sql
-- Created: 2026-01-16
-- Description: Add contact_name, contact_email, contact_phone fields to project_submissions

-- Add contact information columns
ALTER TABLE project_submissions
ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(20);

-- Add index for email lookups
CREATE INDEX IF NOT EXISTS idx_project_submissions_email 
    ON project_submissions(contact_email);

-- Add comments for documentation
COMMENT ON COLUMN project_submissions.contact_name IS 'Full name of the person submitting the project';
COMMENT ON COLUMN project_submissions.contact_email IS 'Email address for contact';
COMMENT ON COLUMN project_submissions.contact_phone IS 'Phone number (India format: 10 digits starting with 6-9)';
