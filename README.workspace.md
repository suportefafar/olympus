# FAFAR services

Olympus coordinates the deployable FAFAR services with Docker Compose. Application repositories live beside `olympus/`; each app keeps its own `.env`. PostgreSQL and MongoDB data use persistent Docker volumes.

- [Olympus operator guide](./olympus/README.md)
- [Hermes](./hermes/README.md)
- [Escuta](./escuta/README.md)
- [ChatRapido](./chatrapido/README.md)
- [Stagemanager](./stagemanager/README.md)
- [Nodus](./nodus/README.md)
- [Ciclum](./ciclum/README.md)
- [Athenas](./athenas/README.md)
- [Design System](./design-system/README.md)
- [Nextcloud — servidor 150.164.110.10](./cloud/README.md)

Run `./olympus/olymctl dev up` after configuring the required local env files and committing the reviewed app templates, or use `--no-pull` to deploy the current checkouts. Local WordPress content lives directly in `institutional-website/html`, `intranet-website/html` and `escuta-website-wp/html`, beside `olympus/`. The development Compose stack mounts the institutional and intranet directories; `wordpress-sync` reads `intranet-website/html`. These directories contain operator-supplied files, uploads and plugins and are not prepared by `olymctl`. The retired Escuta WordPress content is preserved separately from the Rails `escuta/` checkout.
