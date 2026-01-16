-- OMI Global Productions - Project Submissions Schema
-- Migration: 002_project_submissions.sql
-- Created: 2026-01-16
-- Description: Table for storing project submission form data

-- Project submissions table
-- Stores all fields from the project submission form
-- Uses gen_random_uuid() which is built-in to PostgreSQL 13+
CREATE TABLE IF NOT EXISTS project_submissions (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core Narrative section
    title VARCHAR(500),
    logline TEXT,
    synopsis TEXT,
    treatment_url VARCHAR(2048),
    
    -- Visuals & Audio section
    moodboard_url VARCHAR(2048),
    soundtracks TEXT,
    
    -- Talent & Logistics section
    writer_bio TEXT,
    actor_1 VARCHAR(255),
    actor_2 VARCHAR(255),
    actor_3 VARCHAR(255),
    actor_4 VARCHAR(255),
    actor_5 VARCHAR(255),
    actor_6 VARCHAR(255),
    budget NUMERIC(15, 2),
    languages VARCHAR(500),
    
    -- Credentials section
    previous_works TEXT,
    terms_accepted BOOLEAN DEFAULT false,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(255)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_project_submissions_created_at 
    ON project_submissions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_project_submissions_status 
    ON project_submissions(status);

CREATE INDEX IF NOT EXISTS idx_project_submissions_title 
    ON project_submissions(title);

-- Add comment to table
COMMENT ON TABLE project_submissions IS 'Stores project submission form data from the OMI website';

-- Column comments for documentation
COMMENT ON COLUMN project_submissions.title IS 'Project title - name of the vision';
COMMENT ON COLUMN project_submissions.logline IS 'One-sentence hook describing the project';
COMMENT ON COLUMN project_submissions.synopsis IS 'Detailed story summary';
COMMENT ON COLUMN project_submissions.treatment_url IS 'Link to full treatment document (PDF/Cloud)';
COMMENT ON COLUMN project_submissions.moodboard_url IS 'Pinterest, Behance, or PDF link for visual reference';
COMMENT ON COLUMN project_submissions.soundtracks IS 'Spotify playlist or descriptive audio style';
COMMENT ON COLUMN project_submissions.writer_bio IS 'Biography of the writer/storyteller';
COMMENT ON COLUMN project_submissions.actor_1 IS 'Actor recommendation slot 1';
COMMENT ON COLUMN project_submissions.actor_2 IS 'Actor recommendation slot 2';
COMMENT ON COLUMN project_submissions.actor_3 IS 'Actor recommendation slot 3';
COMMENT ON COLUMN project_submissions.actor_4 IS 'Actor recommendation slot 4';
COMMENT ON COLUMN project_submissions.actor_5 IS 'Actor recommendation slot 5';
COMMENT ON COLUMN project_submissions.actor_6 IS 'Actor recommendation slot 6';
COMMENT ON COLUMN project_submissions.budget IS 'Estimated budget in USD';
COMMENT ON COLUMN project_submissions.languages IS 'Primary languages for the project';
COMMENT ON COLUMN project_submissions.previous_works IS 'Links to showreel or portfolio';
COMMENT ON COLUMN project_submissions.terms_accepted IS 'Whether user accepted terms and conditions';
COMMENT ON COLUMN project_submissions.status IS 'Submission status: pending, reviewed, approved, rejected';
