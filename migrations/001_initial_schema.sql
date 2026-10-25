-- =========================================================================
-- BPSC Question Lab v1.0 - Production Supabase PostgreSQL Schema with RLS
-- Run this in your Supabase SQL Editor to initialize cloud storage.
-- =========================================================================

-- 1. QUESTIONS TABLE (Public shared questions + User-owned private questions)
CREATE TABLE IF NOT EXISTS public.questions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    exam TEXT NOT NULL DEFAULT 'BPSC',
    subject TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT 'Uncategorised',
    subtopic TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option CHAR(1) NOT NULL CHECK(correct_option IN ('A','B','C','D')),
    explanation TEXT NOT NULL DEFAULT '',
    distractor_notes TEXT NOT NULL DEFAULT '',
    concept_tested TEXT NOT NULL DEFAULT '',
    question_type TEXT NOT NULL DEFAULT 'Standard MCQ',
    source_type TEXT NOT NULL DEFAULT 'User-added',
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT 'Medium',
    is_ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
);

-- 2. ATTEMPTS TABLE (User attempt records)
CREATE TABLE IF NOT EXISTS public.attempts (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    selected_option TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    error_type TEXT NOT NULL DEFAULT 'Unclassified',
    error_notes TEXT NOT NULL DEFAULT '',
    test_session_id TEXT NOT NULL DEFAULT '',
    time_spent_seconds REAL NOT NULL DEFAULT 0.0,
    confidence_rating TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL DEFAULT 0.0,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
);

-- 3. TEST SESSIONS TABLE (Mock & timed test history)
CREATE TABLE IF NOT EXISTS public.test_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL UNIQUE,
    exam TEXT NOT NULL DEFAULT 'BPSC',
    test_mode TEXT NOT NULL DEFAULT 'Practice',
    total_questions INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    incorrect_count INTEGER NOT NULL,
    unanswered_count INTEGER NOT NULL,
    negative_mark_rate REAL NOT NULL DEFAULT 0.0,
    total_score REAL NOT NULL DEFAULT 0.0,
    time_spent_seconds REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
);

-- 4. REVISION ITEMS TABLE (Adaptive spaced repetition schedule)
CREATE TABLE IF NOT EXISTS public.revision_items (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    due_date DATE NOT NULL,
    interval_days INTEGER NOT NULL DEFAULT 1,
    repetitions INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    last_reviewed_at TIMESTAMPTZ,
    last_outcome TEXT NOT NULL DEFAULT '',
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
);

-- 5. PINNED NOTEBOOK TABLE (Bookmarked questions & error notes)
CREATE TABLE IF NOT EXISTS public.pinned_notebook (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    note TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    pinned_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW()),
    CONSTRAINT uq_user_pinned_question UNIQUE (user_id, question_id)
);

-- 6. RESEARCH NOTES TABLE (Saved current affairs & source summaries)
CREATE TABLE IF NOT EXISTS public.research_notes (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    key_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
    bihar_angle TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
);

-- =========================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- Ensures complete cross-user data isolation.
-- =========================================================================

-- Enable RLS on all tables
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.test_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.revision_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pinned_notebook ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_notes ENABLE ROW LEVEL SECURITY;

-- Questions: Public questions visible to all authenticated users; private questions visible only to owner
CREATE POLICY "Public questions are viewable by everyone"
    ON public.questions FOR SELECT
    USING (is_public = TRUE OR auth.uid() = user_id);

CREATE POLICY "Users can create their own questions"
    ON public.questions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own questions"
    ON public.questions FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own questions"
    ON public.questions FOR DELETE
    USING (auth.uid() = user_id);

-- Attempts: Strictly private to each user
CREATE POLICY "Users can only view their own attempts"
    ON public.attempts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own attempts"
    ON public.attempts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own attempts"
    ON public.attempts FOR UPDATE
    USING (auth.uid() = user_id);

-- Test Sessions: Strictly private to each user
CREATE POLICY "Users can only view their own test sessions"
    ON public.test_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own test sessions"
    ON public.test_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Revision Items: Strictly private to each user
CREATE POLICY "Users can view their own revision schedule"
    ON public.revision_items FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own revision schedule"
    ON public.revision_items FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own revision schedule"
    ON public.revision_items FOR UPDATE
    USING (auth.uid() = user_id);

-- Pinned Notebook: Strictly private to each user
CREATE POLICY "Users can view their own pinned notebook"
    ON public.pinned_notebook FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert into their own pinned notebook"
    ON public.pinned_notebook FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update/delete their own pinned notebook"
    ON public.pinned_notebook FOR ALL
    USING (auth.uid() = user_id);

-- Research Notes: Strictly private to each user
CREATE POLICY "Users can view their own research notes"
    ON public.research_notes FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert/update their own research notes"
    ON public.research_notes FOR ALL
    USING (auth.uid() = user_id);
