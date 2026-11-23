CREATE TABLE career_cache (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	cache_key VARCHAR(64) NOT NULL,
	payload BYTEA NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, cache_key),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE career_sources (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	kind TEXT NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	original BYTEA NOT NULL,
	extraction BYTEA NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, fingerprint),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE career_usage (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	operation TEXT NOT NULL,
	model TEXT NOT NULL,
	tokens INTEGER,
	cost_microusd INTEGER DEFAULT '0' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE career_versions (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	revision INTEGER NOT NULL,
	decisions JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, revision),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE career_proposals (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	application_id UUID NOT NULL,
	baseline_id UUID NOT NULL,
	resume_version_id UUID NOT NULL,
	revision INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id, application_id) REFERENCES applications (user_id, id),
	FOREIGN KEY(user_id, baseline_id) REFERENCES career_sources (user_id, id),
	FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id),
	UNIQUE (user_id, id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
