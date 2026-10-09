# Legacy inventory and migration notes

Inspected source: `current-infra/services-infra` in the planning workspace, including `compose.yaml`, `compose.dev.yaml`, `compose.prod.yaml`, `up.common.sh`, `up.dev.sh`, `up.prod.sh`, and the reverse-proxy Caddyfiles. The distributed plan describes the deployed topology and is treated as inventory, not as the Compose target.

## Verified legacy components

| Area | Evidence from the current tree | Olympus choice |
| --- | --- | --- |
| Main applications | Compose defines WordPress institutional/intranet, development-only Rails intranet stage, Escuta, Chatrapido, Hermes, Stagemanager, Dike, Temis, Prometheus Bot, Design System, Laras 2026, Cronos | Separate services in the Olympus Compose file; Rails intranet stage is available only at `intranet-stage.farmacia.local`; the legacy production `intranet.farmacia.ufmg.br` route remains WordPress |
| Proxy | Caddy routes domains to named app services; dev uses `.local`, production uses `farmacia.ufmg.br` subdomains | One Caddy service on the shared edge network; only 80/443 are published |
| SQL data | The legacy tree has MySQL 5.7 and PostgreSQL 17 named-volume services; MySQL import scripts and PostgreSQL init scripts exist | PostgreSQL remains active and the overlays now provide MySQL plus the three WordPress services. Production still requires a tested MySQL backup/restore and database compatibility review; the old database volume remains untouched |
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
- Legacy production uses MySQL 5.7, while the Olympus overlay selects MySQL 8.0. Review compatibility and perform a tested backup/restore before migrating any production data; do not point this Compose file at the current database volume without that migration plan.
- The old Caddy config references routes and certificates from its own repo. Validate the sibling reverse-proxy repository's paths, domains, TLS material, and backend service names before deployment.
- Several old Compose services and data paths remain outside the new stack: PHPMyAdmin, Mongo Express, Autoheal, stage Escuta, and import scripts. Reintroduce only after an operator confirms they are needed and access controls/data handling are settled.
- This first Compose draft assumes app Dockerfiles build from their repository roots. Confirm actual Dockerfiles, health endpoints, required environment keys, database names, and dependency initialization in each upstream repo.
- Deploy completion currently means `docker compose up` exited successfully. Health-check based readiness and database migration/backup orchestration remain follow-up work.


## Pulled repository audit (2026-10-08)

All verified application repositories listed in the active `apps.tsv` were cloned from or fast-forward-pulled from `main`. The Intranet Rails app is built from its repository and runs beside the WordPress legacy service; the legacy public hostname remains attached to WordPress. No independent institutional app origin was available. The legacy plan states WordPress core/site files are not fully tracked, so those services remain dependent on operator-supplied content and a planned data migration.

The Rails and Node application repositories provide their own Dockerfiles. Escuta's existing env template is under `deploy/`; a root template was added for Olympus' sibling-repository contract. Hermes, ChatRapido, and Stagemanager lacked root templates; their new templates list runtime variables observed in app config. Dike, Design System, Laras 2026, Cronos, and the proxy have root templates noting defaults or the absence of app-specific settings. Local `.env` files are created with mode 0600 and are ignored; templates contain required-value markers only, never generated credentials.
