# Olympus

Olympus is the portable Docker Compose orchestrator for FAFAR services. Its workspace is discovered from this checkout, so commands work regardless of the current directory. See [README.workspace.md](README.workspace.md) for the workspace overview.

## Commands

```sh
./olymctl dev up [app] [--no-pull] [--branch NAME] [--commit SHA]
./olymctl prod up [app] [--no-pull] [--branch NAME] [--commit SHA]
./olymctl prod rollback APP [--commit SHA]
./olymctl history
./olymctl down dev|prod [app]
```

The first `up` prepares missing checkouts from `apps.tsv`, creates `.env` only from a repository's `.env.example`, copies `README.workspace.md` to the workspace root, and then starts the selected Compose services. Missing or placeholder settings stop startup for the affected app.

Compose and repository inventory are initial migration choices based on `current-infra/services-infra`. Review service-specific database variables, health checks, secrets, proxy routes, and data migration before production use. The legacy stack combines application configuration in one root `.env`; this orchestrator deliberately does not carry that file forward.


## Current checkout readiness

The verified app repositories are checked out beside Olympus. The `intranet` main branch currently contains documentation only and has no Dockerfile, while no deployable institutional repository origin was found in the supplied inventory. The institutional, intranet, and legacy Escuta WordPress sites are provided by the Compose overlays using operator-supplied content paths and database credentials; their production data still requires a planned backup and migration.

Every runnable app has a root `.env.example`, a local ignored `.env`, and build-context exclusions for env files and private key material. Replace `__REQUIRED__` entries with operator-provided values. Commit the reviewed templates and ignore rules in each application before a normal pull-enabled `up`; use `--no-pull` to run the local configuration while it remains uncommitted. Do not use the legacy WordPress database volume with the new stack until its backup and migration are planned.

## Production server overrides

`olymctl prod` also loads `compose.prod.local.yaml` when present. This file is ignored by Git and may contain server-specific paths, imported runtime configuration and database image versions. Keep it mode 0600 and back it up with the server secrets. The `production/` directory is also private to the server.

Production mounts `Caddyfile.prod` and the existing TLS certificate directory at runtime. Its routes match the Olympus services; legacy administrative dashboards and staging services are not published by this configuration. Escuta and Hermes storage persists across container replacement.

For a migration, restore logical dumps into fresh database storage before starting apps. Keep the source database major versions for the initial restore (`MYSQL_IMAGE` can select the existing MySQL version). Preserve Rails secrets and Hermes encryption keys associated with the imported data. A VM running MongoDB must expose AVX CPU instructions.

Migration status and server-specific operational notes: [production migration](docs/PRODUCTION-MIGRATION.md). Laras images and PDFs are not tracked by Git; restore its `images/` and `docs/` before building production.
