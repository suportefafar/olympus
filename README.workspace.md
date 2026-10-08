# FAFAR services

Olympus coordinates the deployable FAFAR services with Docker Compose. Application repositories live beside `olympus/`; each app keeps its own `.env`. PostgreSQL and MongoDB data use persistent Docker volumes.

- [Olympus operator guide](./olympus/README.md)
- [Hermes](./hermes/README.md)
- [Escuta](./escuta-website/README.md)
- [ChatRapido](./chatrapido/README.md)
- [Stagemanager](./stagemanager/README.md)
- [Design System](./design-system/README.md)

Run `./olympus/olymctl dev up` after configuring the required local env files and committing the reviewed app templates, or use `--no-pull` to deploy the current checkouts. The legacy Intranet and Institutional WordPress services are not in the active stack because the pulled repositories do not contain deployable source for them yet.
