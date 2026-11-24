# Card-free persistent processing

**Current deployment.** Keep the private Vercel Hobby UI, Render Free FastAPI, Free Postgres and Free Key Value. Render can sleep after 15 minutes, uses an ephemeral filesystem, and restarts can discard Redis data. Neither Vercel requests nor a sleeping Render web service supplies a continuous listener. Oracle signup is unavailable to this owner because card verification is unavailable. No Oracle resources or paid fallback are part of this checkpoint. [Current deployment and expiry](PRIVATE_PREVIEW.md) · [Render limits](https://render.com/docs/free)

| Option | Appropriate work | Constraints and evidence |
|---|---|---|
| Waifly Free, hosted candidate | A small, headless Python worker reading committed tasks from a separately authorized PostgreSQL instance | The provider advertises card-free signup, one continuously running free server, 300 MB RAM and 1 GB storage. The bundled MySQL service cannot replace JODY's PostgreSQL/pgvector dependency. Account eligibility, actual uptime, Python/package support, TLS egress to Neon, secret isolation, restart behavior and memory headroom are unverified. Benchmark only a synthetic no-op worker first. Keep real candidate data, bot sessions and secrets off the service until it passes. No account or resource was created. [Provider offer](https://waifly.com/) |
| Always-on Ubuntu machine | Recommended card-free fallback with the tested application stack; local PostgreSQL/Redis and supervised task execution | Uptime depends on power, Internet, disk, cooling and host restarts. An 8 GB laptop can do light processing. Schedule Tectonic or small local inference separately. Real pairing and provider polling remain disabled. |
| Scheduled GitHub Actions | Optional later, short idempotent reconciliation from durable cursors | Schedules can be delayed or dropped; a job exits and cannot hold a continuous session. Public/private repository plans and runner quotas differ. No polling workflow was activated. [Schedule semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) |

PythonAnywhere lists always-on tasks outside its free plan; alwaysdata documents supervised Services as paid. Neither is assumed to be a free resident worker. [PythonAnywhere plans](https://www.pythonanywhere.com/pricing/) · [alwaysdata Services](https://help.alwaysdata.com/en/docs/web-hosting/services/)

## Ubuntu runbook

1. Use a host the owner controls with Ubuntu 24.04, disk encryption, OS updates and restricted local accounts. Run the existing Compose PG16/pgvector + Redis and API/web stack as described in the [README](../README.md). Use loopback bindings. Keep owner data local or explicitly authorize a dedicated rehearsal DB. The current hosted Render DB and Redis accept only internal connections; a home worker cannot use them directly.
2. The existing worker supports one inert `local_probe` iteration. The checked-in systemd user service and timer repeat **only that operation** after explicit installation. `run_once.py` binds the private owner; it cannot accept an arbitrary tenant from the queue or start an external adapter. Future multi-user workers must claim an authorized tenant-task pair and enforce per-user policy at execution.
3. For an optional local rehearsal, put the **restricted** `JODY_RUNTIME_DATABASE_URL` (SQLAlchemy `postgresql+psycopg://` DSN) and private `REDIS_URL` in mode-0600 `~/.config/jody/worker.env`. Supply neither admin password nor bot, AI or owner secrets. Use the restricted DSN derived during local provisioning, stored through the operator secret manager. `JODY_PRIVATE_PREVIEW=1` forces a no-op. Check the checkout path in the service's WorkingDirectory and ExecStart if installed elsewhere.
4. The following is manual opt-in. First inspect the files and verify while the DB is paused. Leave all external sources and deliveries disabled.

   ```bash
   systemd-analyze --user verify infra/systemd/jody-probe.service infra/systemd/jody-probe.timer
   install -d -m 700 ~/.config/systemd/user
   install -m 644 infra/systemd/jody-probe.{service,timer} ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user start jody-probe.service
   journalctl --user -u jody-probe.service -n 10
   # Enable only for a desired recurring local probe
   systemctl --user enable --now jody-probe.timer
   systemctl --user list-timers jody-probe.timer
   # Stop recurring execution
   systemctl --user disable --now jody-probe.timer
   ```

5. A user timer needs a running user manager. For operation after logout, the host administrator can enable lingering for that service account. Configure the database/broker startup after reboot separately, test restart and disk space, and verify the last durable completion time. Sleep, battery loss, Wi-Fi loss, OS maintenance and thermal throttling interrupt work. A powered-off PC cannot receive jobs. Recover from durable Postgres cursors and expiring leases; rate-limit catch-up and reconcile uncertain deliveries. If trusted third-party persistent compute is unavailable, disclose offline intervals rather than promising 24/7.
6. For a future resident listener, run a dedicated foreground service per permitted adapter with restricted identity, bounded restart backoff, heartbeat and an alert in the private inbox. A minute timer is sufficient for a probe; it cannot preserve a linked-device socket. Use synthetic workloads to measure memory and uptime, confirm account terms and obtain the specific provider's authorization before enabling any listener. Do not bridge the hosted private network by publishing a DB port.
