"""Provision the dedicated local application role with the migration account."""

from psycopg import connect, sql
from sqlalchemy import make_url

from .config import database_url, runtime_url


def provision() -> None:
    admin = make_url(database_url())
    app = runtime_url()
    if app.username == admin.username or not app.password or not app.username:
        raise ValueError("Configure an independent application database login.")
    role = sql.Identifier(app.username)
    with connect(admin.set(drivername="postgresql").render_as_string(hide_password=False)) as db:
        db.execute("SET LOCAL lock_timeout = '60s'")
        db.execute("SELECT pg_advisory_xact_lock(431027115)")
        current = db.execute(
            "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication FROM pg_roles WHERE rolname=%s",
            (app.username,),
        ).fetchone()
        if current is None:
            db.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(role, sql.Literal(app.password))
            )
        elif any(current):
            raise ValueError("Application role must be unprivileged.")
        for grant in [
            "USAGE ON SCHEMA public",
            "SELECT, INSERT ON career_sources, career_versions, career_cache, career_usage, career_proposals, resume_versions, applications",
            "SELECT ON github_projects, approval_requests, companies, blocked_entities",
            "SELECT ON trust_evaluations, generated_artifacts, email_events, recruiter_outreach",
            "UPDATE (is_whitelisted) ON job_sources",
            "INSERT, DELETE ON blocked_entities",
            "UPDATE (reason) ON blocked_entities",
            "UPDATE (tokens) ON career_usage",
            "UPDATE (email,full_name,updated_at) ON users",
            "UPDATE (github_username,linkedin_profile_url,portfolio_url,candidate_revision,candidate_ciphertext,onboarding_steps,updated_at) ON candidate_profiles",
            "SELECT, INSERT, DELETE ON uploaded_resumes",
            "UPDATE (label,target_role) ON uploaded_resumes",
            "SELECT ON alembic_version, users, candidate_profiles, user_settings, system_control, jobs, job_sources, source_observations, job_events, audit_events, idempotency_keys, integration_connections, background_tasks",
            "SELECT, INSERT, DELETE ON sessions",
            "INSERT ON jobs, job_sources, source_observations, job_events, audit_events, idempotency_keys, integration_connections, background_tasks",
            "UPDATE ON user_settings, system_control, integration_connections, background_tasks, idempotency_keys",
            "DELETE ON integration_connections",
            "EXECUTE ON FUNCTION jody_session_owner(text)",
            "EXECUTE ON FUNCTION jody_dispatch_open()",
        ]:
            db.execute(sql.SQL("GRANT " + grant + " TO {}").format(role))


if __name__ == "__main__":
    provision()
