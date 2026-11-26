CREATE TABLE gmail_accounts (
	user_id UUID NOT NULL, 
	account TEXT, 
	"grant" BYTEA, 
	state TEXT DEFAULT 'Disconnected' NOT NULL, 
	history_id TEXT, 
	policy JSONB DEFAULT '{}'::jsonb NOT NULL, 
	last_success TIMESTAMP WITH TIME ZONE, 
	state_hash VARCHAR(64), 
	session_hash VARCHAR(64), 
	verifier BYTEA, 
	expires TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE gmail_runs (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	status TEXT NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	due TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	progress JSONB DEFAULT '{}'::jsonb NOT NULL, 
	counts JSONB DEFAULT '{}'::jsonb NOT NULL, 
	finished TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE gmail_messages (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	account_key VARCHAR(64) NOT NULL, 
	message_key TEXT NOT NULL, 
	classification TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, account_key, message_key), 
	UNIQUE (user_id, id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE gmail_job_evidence (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	message_id UUID NOT NULL, 
	job_id UUID NOT NULL, 
	platform TEXT NOT NULL, 
	needs_review BOOLEAN NOT NULL, 
	facts JSONB DEFAULT '{}'::jsonb NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id, message_id) REFERENCES gmail_messages (user_id, id), 
	FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id), 
	UNIQUE (user_id, message_id, job_id), 
	UNIQUE (user_id, id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
