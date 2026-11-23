"""Private onboarding state and tenant-owned source resume uploads."""

from alembic import op

revision = "0003_candidate"
down_revision = "0002_secure_data"


def upgrade() -> None:
    op.execute("""ALTER TABLE candidate_profiles
        ADD candidate_revision INTEGER NOT NULL DEFAULT 0,
        ADD candidate_ciphertext BYTEA, ADD onboarding_steps JSONB NOT NULL DEFAULT '{}'::jsonb""")
    op.execute("""CREATE TABLE uploaded_resumes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        label VARCHAR(160) NOT NULL, target_role VARCHAR(160),
        byte_size INTEGER NOT NULL CHECK (byte_size BETWEEN 1 AND 5242880),
        ciphertext BYTEA NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(user_id,id))""")
    op.execute("ALTER TABLE uploaded_resumes ENABLE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope ON uploaded_resumes
        USING (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid)
        WITH CHECK (user_id=NULLIF(current_setting('jody.user_id',true),'')::uuid)""")


def downgrade() -> None:
    op.drop_table("uploaded_resumes")
    op.execute("""ALTER TABLE candidate_profiles DROP candidate_revision,
               DROP candidate_ciphertext, DROP onboarding_steps""")
