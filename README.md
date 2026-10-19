# Olympus

Olympus is the portable Docker Compose orchestrator for FAFAR services. Its workspace is discovered from this checkout, so commands work regardless of the current directory. See [README.workspace.md](README.workspace.md) for the workspace overview.

## Commands

The CLI follows the shape `olymctl <ambiente> [--remote] <comando> [flags]`. An environment selects the Compose stack; `--remote` runs the command on that environment's configured remote host. The same remote modifier is also accepted after the command for compatibility.

```sh
olymctl dev up [app|reverse-proxy|postgres-db|mongo-db|mysql-db] [--no-pull] [--branch NAME] [--commit SHA]
olymctl prod up [app] [--no-pull] [--branch NAME] [--commit SHA]
olymctl prod up --prepare-only
olymctl prod rollback APP [--commit SHA]
olymctl dev status
olymctl prod status
olymctl dev ports
olymctl prod ports
olymctl prod --remote up [app] [--no-pull]
olymctl prod --remote up --prepare-only
olymctl prod --remote rollback APP [--commit SHA]
olymctl prod --remote status
olymctl prod --remote ports
olymctl history
olymctl down dev|prod [app]
```

In dev, `olymctl dev up postgres-db`, `olymctl dev up mongo-db` and `olymctl dev up mysql-db` start an individual database service without changing app checkouts.
`reverse-proxy` is also available as an app target: `olymctl dev up reverse-proxy --no-pull`.

The remote production endpoint is currently hardcoded in `olymctl` as `root@150.164.110.1:10022`. Configure the SSH key locally, matching that host in `~/.ssh/config`:

```sshconfig
Host 150.164.110.1
  User root
  IdentityFile ~/.ssh/<private-key>
```

The remote VM must have `olymctl` available on `PATH` (install it once from the server checkout with `sudo ./scripts/install-path.sh`). `status` and `ports` work for both `dev` and `prod` locally. Remote execution currently targets only production; `dev --remote` is not configured yet.

The CLI does not yet have a command to define remote environments. Adding remote environment configuration is a later step; for now the production user, host, and port stay hardcoded in the script, while the SSH key remains in the operator's SSH config.

Unless `--no-pull` is used, `up` first fetches Olympus `origin/main`. If Olympus advances, the CLI switches to that revision and re-executes the same `up` command before preparing application repositories. A dirty Olympus checkout or local commits absent from `origin/main` stop the update. `--no-pull` skips Git updates for both Olympus and the applications. A remote production `up` performs the same Olympus update on the server before invoking its refreshed CLI.

```sh
olymctl prod --remote up
olymctl prod --remote up escuta --no-pull
olymctl prod --remote rollback escuta
olymctl prod --remote rollback escuta --commit abc1234
olymctl dev status
olymctl prod --remote status
olymctl prod --remote ports
```

`status` prints a one-time container snapshot with CPU and RAM usage, health, state, network I/O, and block I/O. Network and block I/O are cumulative since each container started; stopped containers have no live resource sample. `ports` lists ports declared inside each container and host-to-container port mappings. A declared internal port does not prove that an application is listening on it.

`up --prepare-only` syncs the production source checkouts, including the reverse proxy, and prepares app `.env` files from their tracked examples without running Compose. Use it to provision private first-deploy `.env.production` files before the first start.

The first `up` prepares missing checkouts from `apps.tsv` and the reverse proxy, creates `.env` only from a repository's `.env.example`, copies `README.workspace.md` to the workspace root, and then starts the selected Compose services. Missing or placeholder settings stop startup for the affected app.

Compose and repository inventory are initial migration choices based on `current-infra/services-infra`. Review service-specific database variables, health checks, secrets, proxy routes, and data migration before production use. The legacy stack combines application configuration in one root `.env`; this orchestrator deliberately does not carry that file forward.


## Escuta project rename

Escuta now uses `git@github.com:suportefafar/escuta.git`, the `escuta/` checkout,
and the `escuta` Compose service. `up escuta` (including remote production)
migrates an existing clean `escuta-website/` checkout before preparing the app,
preserving its private env files, configuration and attachments. Python 3 is
required for this one-time transition. The command refuses conflicting paths,
uncommitted legacy changes, unexpected origins or duplicate override services.

The same supported workflow updates the service and checkout paths in a private
production override and keeps a mode-0600 backup. External legacy storage paths
and database names remain intact. Rollback lookup also recognizes historical
deployment records under the old service name. The cleanup overlay keeps the
retired service names disabled. Deploy the app, Olympus and reverse-proxy
revisions together through `olymctl prod --remote up escuta`.

## Current checkout readiness

The verified app repositories are checked out beside Olympus. The Rails intranet runs only in development at `intranet-stage.farmacia.local`; the development WordPress intranet uses `intranet.farmacia.local`; the existing `intranet.farmacia.ufmg.br` route remains on legacy WordPress. The app manifest supports an optional environment scope for applications that are not deployed everywhere. No deployable institutional repository origin was found in the supplied inventory. The institutional and Intranet WordPress sites are provided by the Compose overlays using operator-supplied content paths and database credentials.

Every runnable app has a root `.env.example`, a local ignored `.env`, and build-context exclusions for env files and private key material. Replace `__REQUIRED__` entries with operator-provided values. Commit the reviewed templates and ignore rules in each application before a normal pull-enabled `up`; use `--no-pull` to run the local configuration while it remains uncommitted. Do not use the legacy WordPress database volume with the new stack until its backup and migration are planned.

## Production server overrides

`olymctl prod` also loads `compose.prod.local.yaml` when present. This file is ignored by Git and may contain server-specific paths, imported runtime configuration and database image versions. Keep it mode 0600 and back it up with the server secrets. The `production/` directory is also private to the server.

Olympus is an orchestrator and has no container of its own. It brings together the application, database, and reverse-proxy services. The Caddy Compose fragments, Docker build, routes, TLS settings, and access logs live in the sibling `reverse-proxy/` repository. `olymctl` includes that repository's `compose.olympus.yaml` and environment overlay in the same Compose project so Caddy can reach application containers over the shared `edge` network. The proxy repository owns its TLS certificate path in `reverse-proxy/.env`.

For a migration, restore logical dumps into fresh database storage before starting apps. Keep the source database major versions for the initial restore (`MYSQL_IMAGE` can select the existing MySQL version). Preserve Rails secrets and Hermes encryption keys associated with the imported data. A VM running MongoDB must expose AVX CPU instructions.

Migration status and server-specific operational notes: [production migration](docs/PRODUCTION-MIGRATION.md). Laras images and PDFs are not tracked by Git; restore its `images/` and `docs/` before building production.

Development and production routes and Caddy configuration live in `reverse-proxy/web-server/Caddyfile.olympus.dev` and `Caddyfile.olympus.prod`. Olympus still prepares development host entries in `/etc/hosts`; that is part of setting up the local environment, not proxy configuration. Dev uses only `*.farmacia.local`; production `*.farmacia.ufmg.br` names use normal DNS. See [local development setup](docs/DEV-ENVIRONMENT.md); proxy details are documented in the [reverse-proxy integration guide](https://github.com/suportefafar/reverse-proxy/blob/main/docs/OLYMPUS-INTEGRATION.md).

The dev override publishes Dike on `127.0.0.1:3002` and PostgreSQL/MySQL/MongoDB on `127.0.0.1:5432`, `:3306`, and `:27017`. It serves Nodus at `nodus.farmacia.local` and Ciclum at `ciclum.farmacia.local`; both use the shared `postgres-db`, with separate databases. Production also serves both through the shared reverse proxy and uses the same shared PostgreSQL service. Nodus has separate primary/cache/queue/cable databases; Ciclum uses `ciclum_production`. App storage volumes hold uploaded files.

## Preparing Nodus and Ciclum for production

The production definitions are present, but the services have not been deployed. Before the first production `up`, create `nodus/.env.production` from its example, set `SECRET_KEY_BASE` and a provider API key. Create `ciclum/.env.production` from its example and set `RAILS_MASTER_KEY` from the Ciclum credentials key. Both services use `POSTGRES_USER` and `POSTGRES_PASSWORD` from the private `olympus/.env`. Do not commit the app production files.

Confirm DNS for both domains points to the production proxy and that the installed TLS certificate covers both names. Review whether Nodus has existing data to migrate into its databases on the shared PostgreSQL server. Back up the shared `postgres-data` volume, `nodus-storage`, and `ciclum-storage` with the other production data.

## Athenas

O app `athenas` está registrado em desenvolvimento e produção, nos domínios `athenas.farmacia.local` e `athenas.farmacia.ufmg.br`. Use `olymctl dev up athenas --no-pull` para iniciar localmente e `olymctl prod --remote up athenas` para publicar. O grupo inclui web/worker/Ollama e inicializadores idempotentes de banco/modelo. Ele compartilha `postgres-db` com banco separado e storage persistente; os overlays instalam pgvector no PostgreSQL 17. Antes do primeiro deploy, configure `athenas/.env` no servidor a partir de `.env.production.example`, incluindo segredo Rails, administrador inicial e SMTP. Consulte [preparação local](docs/DEV-ENVIRONMENT.md#athenas), o [README do Athenas](../athenas/README.md) e o [guia de migração de produção](docs/PRODUCTION-MIGRATION.md).
