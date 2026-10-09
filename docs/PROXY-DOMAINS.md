# Proxy domains by environment

The Compose environment chooses a distinct Caddyfile:

- `olymctl dev` mounts `Caddyfile.dev`. It serves `*.farmacia.local` with Caddy's internal development certificates.
- `olymctl prod` mounts `Caddyfile.prod`. It serves `*.farmacia.ufmg.br` with the installed production certificate.

The local development command must register only `*.farmacia.local` in `/etc/hosts`. Production `*.farmacia.ufmg.br` names must use normal DNS and resolve to the production VM. Earlier Olympus versions also mapped official `.ufmg.br` names to `127.0.0.1`; the updated `olymctl dev up` removes only those Olympus-managed stale mappings, preserves `.local`, and saves a backup before editing `/etc/hosts`. If passwordless sudo is unavailable, it lists the stale names and leaves `/etc/hosts` untouched.

The active production proxy was compared with the previous production Caddyfile and validates successfully on the VM. Its host routes point at services on the shared Docker edge network. The Caddyfile cannot create public DNS records; `dike.farmacia.ufmg.br` currently has no DNS answer and needs a DNS A record pointing to `150.164.110.1` before that hostname can be reached externally.

`reverse-proxy/Caddyfile` is the legacy single-file configuration driven by `CADDY_ENVIRONMENT` and `DOMAIN_SUFFIX`. Olympus uses the explicit per-environment files above so local development TLS and the installed production certificate cannot be mixed by an environment variable.
