# Codex API on the AI host

Deploy from a clean, pushed Olympus `main` checkout:

```bash
./olymctl prod --remote up codex-api
```

The workflow archives the pushed Olympus commit to `root@150.164.110.3`, installs an isolated `codex-api` service account, copies the already logged-in Codex CLI credentials on first deployment, and starts the HTTP adapter behind Nginx. It replaces the old public DeepSeek route on port 8084; DeepSeek remains on its internal port 18084 and is exposed on port 8086. Port 8085 remains reserved for SSH.

The API uses HTTPS with a server certificate created on first deployment and saved under `/etc/codex-api/`. Clients must trust that certificate explicitly. The certificate and gateway bearer token remain stable on subsequent deploys. The token is stored only in `/etc/codex-api/.env.production` (mode 600); the private Codex login is stored under `/var/lib/codex-api/.codex/` (mode 600). Neither enters Git or deployment logs.

Authenticated endpoints:

- `GET https://150.164.110.3:8084/v1/models`
- `POST https://150.164.110.3:8084/v1/chat/completions`

POST body example:

```json
{"model":"gpt-6.1-sol","reasoning_effort":"medium","messages":[{"role":"user","content":"Olá"}]}
```

Send `Authorization: Bearer <token>`. The API accepts text messages and non-streaming requests. Models are restricted by `CODEX_ALLOWED_MODELS` in the private environment file. Reasoning effort accepts `low`, `medium`, `high`, `xhigh`, and `max`; the selected model must support the chosen value. The service limits request size and concurrency and runs Codex with a read-only sandbox and no approval prompts.

To check the service without displaying secrets:

```bash
ssh root@150.164.110.3 'systemctl is-active codex-api; curl --fail --silent --show-error --cacert /etc/codex-api/tls.crt https://150.164.110.3:8084/healthz'
```
