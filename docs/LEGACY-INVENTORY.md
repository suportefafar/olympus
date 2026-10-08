# Legacy inventory and migration notes

Inspected source: `current-infra/services-infra` in the planning workspace, including `compose.yaml`, `compose.dev.yaml`, `compose.prod.yaml`, `up.common.sh`, `up.dev.sh`, `up.prod.sh`, and the reverse-proxy Caddyfiles. The distributed plan describes the deployed topology and is treated as inventory, not as the Compose target.

## Verified legacy components

| Area | Evidence from the current tree | Olympus choice |
| --- | --- | --- |
| Main applications | Compose defines WordPress institutional/intranet, Escuta, Chatrapido, Hermes, Stagemanager, Dike, Temis, Prometheus Bot, Design System, Laras 2026, Cronos | Separate services in the Olympus Compose file; no Stage environment is included |
| Proxy | Caddy routes domains to named app services; dev uses `.local`, production uses `farmacia.ufmg.br` subdomains | One Caddy service on the shared edge network; only 80/443 are published |
| SQL data | The legacy tree has MySQL 5.7 and PostgreSQL 17 named-volume services; MySQL import scripts and PostgreSQL init scripts exist | PostgreSQL is active in the current Compose. MySQL and WordPress are deferred because the site source is not deployable from the verified repos; the old database remains untouched and out of this stack |
| Mongo | MongoDB named volume; Prometheus Bot depends on it | Persistent named volume retained |
| Writable application data | ChatRapido and Stagemanager bind `storage/`; WordPress site files are bind-mounted under `institutional-website/html` and `intranet-website/html` | Rails storage binds are retained; WordPress content needs a separately designed import/persistence setup |
| Development hosts | `up.dev.sh` adds local names to `/etc/hosts`, then runs Compose with a local Caddyfile | CLI adds missing manifest hostnames idempotently and reports privilege failures |
| Secrets/config | Legacy stack interpolates many values from one `services-infra/.env`; `up.common.sh` reads it as shell input | Not carried over. App runtime settings must live in each app's `.env`; database bootstrap values belong to Olympus `.env` only |
| Build | Most services build from directories in the legacy checkout; some use direct `env_file`; build runs locally | Builds remain local. New contexts point to sibling repositories and require review against each app's actual Dockerfile |

## Repository origin evidence

The legacy subdirectories had these configured origins when inspected: `intranet`, `hermes`, `escuta-website`, `chatrapido`, `stagemanager`, `dike`, `temis`, `prometheus-bot`, `design-system`, `laras2026-website`, `cronos`, and `reverse-proxy` point to corresponding `suportefafar` repositories. The `institutional` directory had no configured origin. The legacy helper also clones WordPress themes/plugins into the old `*-website/html/wp-content` trees; those are not silently mapped to a new content repository here.

`apps.tsv` preserves the verified origins and leaves the institutional URL blank. Supply its correct independently maintained repository (and decide the WordPress content migration) before a full `up` can work. This prevents a guessed clone source.

## Operational differences and open migration work

- Legacy `compose.dev.yaml` exposes many development ports and the old production overlay binds application ports to `10.10.10.2`; Olympus only publishes the Caddy ports.
- Legacy production uses MySQL 5.7, while the initial Olympus file selects MySQL 8.4. Review compatibility and perform a tested backup/restore before migrating any production data; do not point this Compose file at the current database volume.
- The old Caddy config references routes and certificates from its own repo. Validate the sibling reverse-proxy repository's paths, domains, TLS material, and backend service names before deployment.
- Several old Compose services and data paths are intentionally absent from the new stack: MySQL/WordPress, PHPMyAdmin, Mongo Express, Autoheal, stage Escuta, WordPress content trees, and import scripts. Reintroduce only after an operator confirms they are needed and access controls/data handling are settled.
- This first Compose draft assumes app Dockerfiles build from their repository roots. Confirm actual Dockerfiles, health endpoints, required environment keys, database names, and dependency initialization in each upstream repo.
- Deploy completion currently means `docker compose up` exited successfully. Health-check based readiness and database migration/backup orchestration remain follow-up work.


## Pulled repository audit (2026-10-08)

All verified application repositories listed in the active `apps.tsv` were cloned from or fast-forward-pulled from `main`. `intranet` was already at the current main commit but contains documentation, no application source, and no Dockerfile. No independent institutional app origin was available. The legacy plan states WordPress core/site files are not fully tracked, so those services are excluded from the build list until an operator supplies the deployable source and data migration.

The Rails and Node application repositories provide their own Dockerfiles. Escuta's existing env template is under `deploy/`; a root template was added for Olympus' sibling-repository contract. Hermes, ChatRapido, and Stagemanager lacked root templates; their new templates list runtime variables observed in app config. Dike, Design System, Laras 2026, Cronos, and the proxy have root templates noting defaults or the absence of app-specific settings. Local `.env` files are created with mode 0600 and are ignored; templates contain required-value markers only, never generated credentials.
