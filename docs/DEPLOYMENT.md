# Deployment

The supported deployment is a single-user localhost service or a private host reached through SSH. The application has no identity or tenant boundary. Keep both published ports bound to loopback. Run one backend worker.

## Container startup

Install Docker Engine/Desktop and Compose 2.24+. The optional `.env` file uses Compose’s [optional env-file support](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

```bash
test -f .env || cp .env.example .env
chmod 600 .env
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
curl --fail http://127.0.0.1:4173/ready
```

Open http://127.0.0.1:4173. Simulated mode works with empty credentials. The health check confirms database/checkpointer readiness; provider readiness flags indicate configuration presence only.

If localhost port 8000 is already in use, select a free backend port without stopping the existing process:

```bash
export JA_BACKEND_PORT=8001
docker compose up -d --build --wait --wait-timeout 120
```

The frontend port remains 4173 to preserve the explicit allowed browser origins. Stop any previous instance of this application on that port before starting its container, or use the development frontend on the supported 5173 origin. Do not terminate unrelated processes.

## Images and proxy

The backend installs its locked Python dependencies and runs under UID 10001. The frontend uses a multi-stage build: Node compiles the assets, then [unprivileged Nginx](https://github.com/nginx/docker-nginx-unprivileged) serves them on container port 8080. Node and frontend development dependencies are absent from the runtime stage.

Nginx proxies `/api/` and `/ready` to the internal backend, supports WebSocket upgrades, and preserves the backend’s localhost Host check. Static asset filenames receive long-lived caching; application entry routes revalidate. The request-body limit accommodates the application’s bounded JPEG payload.

Credentials are passed to the backend at runtime. `.env`, local data, dependency caches, and the local artifact workspace are excluded from image build contexts. API keys are never frontend build arguments.

## Private remote host

After publishing your source repository, substitute its actual URL below:

```bash
git clone https://github.com/YOUR_USER/judgment-apprentice.git
cd judgment-apprentice
cp .env.example .env
chmod 600 .env
# Edit .env locally on the host if live providers are needed.
docker compose up -d --build --wait --wait-timeout 120
```

From your own machine, use an authenticated SSH tunnel:

```bash
ssh -N -L 4173:127.0.0.1:4173 YOUR_USER@YOUR_HOST
```

Open http://127.0.0.1:4173 on your machine. This also preserves a browser localhost secure context for capture permissions. Do not publish these container ports on `0.0.0.0` or attach an anonymous public reverse proxy. A public service would require application authentication, resource ownership, HTTPS, and abuse controls first.

## Persistence and updates

Sessions, evidence, maps, and workflow checkpoints live in the named `judgment-data` volume mounted at `/app/data`. Local development uses the separate root `data/` directory. `docker compose down` preserves the volume; `docker compose down -v` deletes it.

Take a consistent backup with the backend stopped. Store the archive outside the repository and protect it as sensitive captured data:

```bash
mkdir -p "$HOME/judgment-apprentice-backups"
docker compose stop backend
docker compose cp backend:/app/data "$HOME/judgment-apprentice-backups/data-$(date +%Y%m%d-%H%M%S)"
docker compose start backend
```

Keep a backup before updating code or changing the data schema. Restore only with the backend stopped, and preserve ownership for UID 10001. Startup supports the legacy session formats covered by the storage tests; arbitrary old or modified databases are not guaranteed compatible.

For an update, after making a backup:

```bash
git pull --ff-only
docker compose up -d --build --wait --wait-timeout 120
```

## Troubleshooting and verification

- An occupied port: inspect `docker compose ps` and the local listener; change `JA_BACKEND_PORT` where appropriate.
- An unhealthy backend: use `docker compose logs --tail=100 backend`; check data-volume permissions and configuration. Never paste credentials into diagnostics.
- A broken proxy: compare `http://127.0.0.1:4173/ready` with the published backend’s `/ready`, then inspect frontend logs.
- A live-provider setup error: follow [LIVE_SETUP.md](LIVE_SETUP.md). A healthy container does not prove a valid provider account.

GitHub CI builds both images, waits for health, verifies the proxied SPA/API routes, creates and deletes a simulated session, and checks the WebSocket event connection. No credentials or paid provider requests are required. Docker is not installed on the current development machine, so that container runtime check remains pending until a Docker-capable environment runs it.
