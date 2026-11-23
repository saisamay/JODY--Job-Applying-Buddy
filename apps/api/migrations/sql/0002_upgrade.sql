CREATE TYPE job_source_enum AS ENUM ('whatsapp', 'linkedin_feed', 'linkedin_post', 'manual');

CREATE TYPE job_status_enum AS ENUM ('discovered', 'pending_approval', 'tailoring', 'applied', 'outreach_active', 'shortlisted', 'assessment', 'interview', 'offer', 'rejected', 'scam_blocked', 'skipped');

CREATE TYPE apply_method_enum AS ENUM ('cold_email', 'linkedin_easy_apply', 'greenhouse', 'lever', 'workday', 'wellfound', 'internshala', 'custom_portal');

CREATE TYPE outreach_status_enum AS ENUM ('queued', 'connect_sent', 'accepted', 'dm_sent', 'followup_sent', 'replied', 'failed');

CREATE TYPE email_class_enum AS ENUM ('application_ack', 'assessment', 'shortlist_interview', 'offer', 'rejection', 'scam_spam', 'unrelated');

ALTER TABLE owners RENAME TO users;
ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE users ADD email varchar(255), ADD full_name varchar(255) NOT NULL DEFAULT 'Private owner',
 ADD is_active boolean NOT NULL DEFAULT true, ADD created_at timestamptz NOT NULL DEFAULT now(),
 ADD updated_at timestamptz NOT NULL DEFAULT now();
INSERT INTO users(id) VALUES ('00000000-0000-4000-8000-000000000001') ON CONFLICT DO NOTHING;
UPDATE users SET email = id::text || '@private.invalid';
ALTER TABLE users ALTER email SET NOT NULL, ADD UNIQUE(email), ALTER full_name DROP DEFAULT;

ALTER TABLE sessions RENAME COLUMN owner_id TO user_id;

ALTER TABLE sessions DROP CONSTRAINT sessions_owner_id_fkey, ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE jobs RENAME COLUMN owner_id TO user_id;

ALTER TABLE jobs ALTER id SET DEFAULT gen_random_uuid();

ALTER TABLE jobs DROP CONSTRAINT jobs_owner_id_fkey, ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE source_observations RENAME COLUMN owner_id TO user_id;

ALTER TABLE source_observations ALTER id SET DEFAULT gen_random_uuid();

ALTER TABLE source_observations ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE, ADD UNIQUE(user_id,id);

ALTER TABLE job_events RENAME COLUMN owner_id TO user_id;

ALTER TABLE job_events ALTER id SET DEFAULT gen_random_uuid();

ALTER TABLE job_events ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE, ADD UNIQUE(user_id,id);

ALTER TABLE jobs ADD role text, ADD location text, ADD is_remote boolean, ADD application_url text,
 ADD recruiter_email varchar(255), ADD company_id uuid, ADD status job_status_enum NOT NULL DEFAULT 'discovered';
ALTER TABLE source_observations ALTER source TYPE job_source_enum USING source::job_source_enum, ADD source_id uuid;
ALTER TABLE job_events ALTER kind TYPE job_status_enum USING kind::job_status_enum;

CREATE TABLE system_control (
	singleton BOOLEAN NOT NULL,
	is_system_paused BOOLEAN DEFAULT true NOT NULL,
	PRIMARY KEY (singleton),
	CHECK (singleton)
);

CREATE TABLE audit_events (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	action TEXT NOT NULL,
	resource_id UUID,
	details JSONB DEFAULT '{}'::jsonb NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE background_tasks (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	kind TEXT NOT NULL,
	status TEXT DEFAULT 'pending' NOT NULL,
	next_publish_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (status IN ('pending','succeeded','failed')),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE blocked_entities (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	kind TEXT NOT NULL,
	value TEXT NOT NULL,
	reason TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (kind IN ('company','domain','email')),
	UNIQUE (user_id, kind, value),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE candidate_profiles (
	user_id UUID NOT NULL,
	github_username VARCHAR(100),
	linkedin_profile_url TEXT,
	portfolio_url TEXT,
	telegram_chat_id BIGINT,
	resume_git_repo_url TEXT,
	resume_master_branch VARCHAR(50) DEFAULT 'main',
	master_latex_template TEXT,
	profile_vault_json JSONB DEFAULT '{}'::jsonb NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	UNIQUE (telegram_chat_id)
);

CREATE TABLE companies (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	name TEXT NOT NULL,
	domain TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE github_projects (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	repo_url TEXT NOT NULL,
	commit_sha TEXT NOT NULL,
	description TEXT,
	readme_summary TEXT,
	tech_stack JSONB,
	live_links JSONB,
	verified_metrics JSONB DEFAULT '{}'::jsonb NOT NULL,
	embedding VECTOR,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, repo_url, commit_sha),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE idempotency_keys (
	user_id UUID NOT NULL,
	key UUID NOT NULL,
	request_digest VARCHAR(64) NOT NULL,
	response JSONB DEFAULT '{}'::jsonb NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (user_id, key),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE integration_connections (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	provider TEXT NOT NULL,
	encrypted_credentials BYTEA NOT NULL,
	credentials_iv BYTEA NOT NULL,
	key_version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (octet_length(credentials_iv) = 12 AND octet_length(encrypted_credentials) >= 16),
	UNIQUE (user_id, provider),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE job_sources (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	kind job_source_enum NOT NULL,
	identifier TEXT NOT NULL,
	is_whitelisted BOOLEAN DEFAULT false NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, kind, identifier),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE user_settings (
	user_id UUID NOT NULL,
	min_trust_score_auto_apply INTEGER DEFAULT '80' NOT NULL,
	min_ats_score_threshold INTEGER DEFAULT '82' NOT NULL,
	max_daily_linkedin_connects INTEGER DEFAULT '12' NOT NULL,
	max_daily_linkedin_dms INTEGER DEFAULT '20' NOT NULL,
	outbound_enabled BOOLEAN DEFAULT false NOT NULL,
	auto_trash_scams BOOLEAN DEFAULT false NOT NULL,
	auto_archive_rejections BOOLEAN DEFAULT false NOT NULL,
	PRIMARY KEY (user_id),
	CHECK (min_trust_score_auto_apply BETWEEN 0 AND 100 AND min_ats_score_threshold BETWEEN 0 AND 100),
	CHECK (max_daily_linkedin_connects BETWEEN 0 AND 1000 AND max_daily_linkedin_dms BETWEEN 0 AND 1000),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE resume_versions (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	latex_source TEXT NOT NULL,
	template_revision TEXT NOT NULL,
	job_id UUID,
	claim_manifest JSONB DEFAULT '{}'::jsonb NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE trust_evaluations (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	job_id UUID NOT NULL,
	score INTEGER NOT NULL,
	risk_flags JSONB NOT NULL,
	evidence JSONB DEFAULT '{}'::jsonb NOT NULL,
	rules_version TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id),
	CHECK (score BETWEEN 0 AND 100),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE applications (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	job_id UUID NOT NULL,
	method apply_method_enum NOT NULL,
	status job_status_enum DEFAULT 'discovered' NOT NULL,
	resume_version_id UUID,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id),
	FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id),
	UNIQUE (user_id, job_id, method),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE generated_artifacts (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	resume_version_id UUID,
	job_id UUID NOT NULL,
	kind TEXT NOT NULL,
	storage_key TEXT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	ats_score INTEGER,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id),
	FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id),
	CHECK (sha256 ~ '^[0-9a-f]{64}$'),
	CHECK (ats_score BETWEEN 0 AND 100),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE application_statuses (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	application_id UUID NOT NULL,
	status job_status_enum NOT NULL,
	reason TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, application_id) REFERENCES applications (user_id, id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE approval_requests (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	application_id UUID,
	action TEXT NOT NULL,
	destination TEXT NOT NULL,
	content_digest VARCHAR(64) NOT NULL,
	status TEXT DEFAULT 'pending' NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, application_id) REFERENCES applications (user_id, id),
	CHECK (content_digest ~ '^[0-9a-f]{64}$'),
	CHECK (status IN ('pending','approved','rejected','consumed','revoked')),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE email_events (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	application_id UUID,
	message_id TEXT NOT NULL,
	event_key TEXT NOT NULL,
	classification email_class_enum NOT NULL,
	previous_labels JSONB DEFAULT '{}'::jsonb NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, application_id) REFERENCES applications (user_id, id),
	UNIQUE (user_id, event_key),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE recruiter_outreach (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	application_id UUID NOT NULL,
	recipient TEXT NOT NULL,
	draft TEXT NOT NULL,
	status outreach_status_enum DEFAULT 'queued' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, application_id) REFERENCES applications (user_id, id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

ALTER TABLE jobs ADD FOREIGN KEY(user_id,company_id) REFERENCES companies(user_id,id);
ALTER TABLE source_observations ADD FOREIGN KEY(user_id,source_id) REFERENCES job_sources(user_id,id);
INSERT INTO system_control(singleton) VALUES(true);
INSERT INTO candidate_profiles(user_id) SELECT id FROM users;
INSERT INTO user_settings(user_id) SELECT id FROM users;
INSERT INTO job_sources(user_id,kind,identifier) SELECT DISTINCT user_id,source,'manual' FROM source_observations;
UPDATE source_observations o SET source_id=s.id FROM job_sources s
 WHERE o.user_id=s.user_id AND o.source=s.kind AND s.identifier='manual';
CREATE FUNCTION jody_init_profile() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 INSERT INTO public.candidate_profiles(user_id) VALUES(NEW.id);
 INSERT INTO public.user_settings(user_id) VALUES(NEW.id);
 RETURN NEW;
END $$;
CREATE TRIGGER init_private_profile AFTER INSERT ON users FOR EACH ROW EXECUTE FUNCTION jody_init_profile();

-- Bootstrap authentication with one opaque digest. The API role cannot enumerate sessions without scope.
CREATE FUNCTION jody_session_owner(p_digest text) RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
 SET search_path=pg_catalog AS $$
 SELECT s.user_id FROM public.sessions s JOIN public.users u ON u.id=s.user_id
 WHERE s.digest=p_digest AND s.expires_at>now() AND u.is_active
$$;
REVOKE ALL ON FUNCTION jody_session_owner(text) FROM PUBLIC;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON users USING (id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON audit_events USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE background_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON background_tasks USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE blocked_entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON blocked_entities USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE candidate_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON candidate_profiles USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON companies USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE github_projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON github_projects USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON idempotency_keys USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE integration_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON integration_connections USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE job_sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON job_sources USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON sessions USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON user_settings USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON jobs USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE job_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON job_events USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON resume_versions USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE source_observations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON source_observations USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE trust_evaluations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON trust_evaluations USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON applications USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE generated_artifacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON generated_artifacts USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE application_statuses ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON application_statuses USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON approval_requests USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE email_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON email_events USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE recruiter_outreach ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON recruiter_outreach USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid) WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid);

ALTER TABLE system_control ENABLE ROW LEVEL SECURITY;
CREATE POLICY read_gate ON system_control FOR SELECT USING (true);
CREATE POLICY change_gate ON system_control FOR UPDATE USING (NULLIF(current_setting('jody.user_id',true),'')::uuid='00000000-0000-4000-8000-000000000001');

-- One row lock orders worker claims and the operator's pause transaction across all users.
CREATE FUNCTION jody_dispatch_open() RETURNS boolean LANGUAGE sql VOLATILE SECURITY DEFINER
 SET search_path=pg_catalog AS $$
 SELECT NOT is_system_paused FROM public.system_control WHERE singleton FOR SHARE
$$;
REVOKE ALL ON FUNCTION jody_dispatch_open() FROM PUBLIC;
CREATE FUNCTION jody_task_transition() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP = 'INSERT' AND NEW.status <> 'pending' THEN
   RAISE EXCEPTION 'Tasks must start pending' USING ERRCODE='23514';
 ELSIF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
   IF OLD.status <> 'pending' OR NEW.kind <> 'local_probe' OR public.jody_dispatch_open() IS NOT TRUE THEN
     RAISE EXCEPTION 'Task transition denied' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_task BEFORE INSERT OR UPDATE OF status ON background_tasks
 FOR EACH ROW EXECUTE FUNCTION jody_task_transition();
