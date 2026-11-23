-- Disposable tenant evidence and workflow records for schema/ownership regression tests.
WITH company AS (
 INSERT INTO companies(user_id,name,domain) SELECT user_id,'Fixture Company','example.invalid'
 FROM jobs WHERE description='Legacy fixture vacancy' RETURNING *
)
UPDATE jobs SET company_id=company.id FROM company WHERE jobs.user_id=company.user_id;

WITH job AS (SELECT * FROM jobs WHERE description='Legacy fixture vacancy'),
resume AS (
 INSERT INTO resume_versions(user_id,job_id,latex_source,template_revision)
 SELECT user_id,id,'Synthetic text','fixture-v1' FROM job RETURNING *
), artifact AS (
 INSERT INTO generated_artifacts(user_id,resume_version_id,job_id,kind,storage_key,sha256)
 SELECT user_id,id,job_id,'resume_pdf','fixture-only',repeat('c',64) FROM resume
), application AS (
 INSERT INTO applications(user_id,job_id,method,resume_version_id)
 SELECT user_id,job_id,'cold_email',id FROM resume RETURNING *
), approval AS (
 INSERT INTO approval_requests(user_id,application_id,action,destination,content_digest,expires_at)
 SELECT user_id,id,'draft_review','fixture@example.invalid',repeat('d',64),now()+interval '1 day' FROM application
), outreach AS (
 INSERT INTO recruiter_outreach(user_id,application_id,recipient,draft)
 SELECT user_id,id,'fixture@example.invalid','Synthetic draft' FROM application
), email AS (
 INSERT INTO email_events(user_id,application_id,message_id,event_key,classification)
 SELECT user_id,id,'fixture-message','fixture-event','application_ack' FROM application
), stages AS (
 INSERT INTO application_statuses(user_id,application_id,status) SELECT user_id,id,'discovered' FROM application
), blocked AS (
 INSERT INTO blocked_entities(user_id,kind,value,reason) SELECT user_id,'domain','blocked.invalid','Fixture' FROM job
), project AS (
 INSERT INTO github_projects(user_id,repo_url,commit_sha,embedding)
 SELECT user_id,'https://example.invalid/fixture','fixture-rev','[1,2]'::vector FROM job
)
INSERT INTO trust_evaluations(user_id,job_id,score,risk_flags,rules_version)
 SELECT user_id,id,45,'["unknown_domain"]','fixture-v1' FROM job;
