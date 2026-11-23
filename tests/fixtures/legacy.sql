-- Synthetic pre-upgrade owner, job, source, event and deliberately expired session.
INSERT INTO owners VALUES ('11111111-1111-4111-8111-111111111111');
INSERT INTO sessions VALUES (repeat('a',64),'11111111-1111-4111-8111-111111111111','2000-01-01');
INSERT INTO jobs(id,owner_id,fingerprint,description) VALUES
 ('22222222-2222-4222-8222-222222222222','11111111-1111-4111-8111-111111111111',repeat('b',64),'Legacy fixture vacancy');
INSERT INTO source_observations VALUES
 (gen_random_uuid(),'11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','manual',now());
INSERT INTO job_events VALUES
 (gen_random_uuid(),'11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','discovered',now());
