# Docker & Railway Deployment

> Docker docs: https://docs.docker.com
> Railway docs: https://docs.railway.app

## Docker concepts (what you need for this project)

### Dockerfile

A Dockerfile is a recipe for building a container image — an isolated, reproducible environment with your app and all its dependencies.

```dockerfile
# Our Dockerfile, annotated:

# Base image — slim Python 3.12 (Debian-based, ~150MB)
FROM python:3.12-slim

# Install system dependency (tesseract for OCR)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies (cached layer — only rebuilds when lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy app code (changes more often, so this layer is last)
COPY . .

# Pre-parse PDFs at build time
RUN uv run python main.py || true

# Expose Streamlit's default port
EXPOSE 8501

# Start the app
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Key Dockerfile concepts

**Layers:** Each `RUN`, `COPY`, `FROM` creates a layer. Docker caches layers — if a layer's inputs haven't changed, it reuses the cached version. That's why we copy `pyproject.toml` + `uv.lock` before the rest of the code: dependency installation is slow but rarely changes.

**`--no-install-recommends`:** Installs only the package itself, not suggested extras. Keeps the image small.

**`COPY --from=`:** Multi-stage copy. We grab the `uv` binary from its official image without installing it from source.

**`|| true`:** The `RUN uv run python main.py || true` won't fail the build if parsing errors occur (e.g., missing PDFs).

**`--server.address=0.0.0.0`:** By default, Streamlit listens on `127.0.0.1` (localhost), which is local *inside the container*. When Docker maps `8501:8501`, it forwards from the host to the container's network. But the container's `127.0.0.1` is unreachable from outside. `0.0.0.0` tells Streamlit to listen on all network interfaces, making it reachable from the host.

**`uv sync --frozen --no-dev`:** `--frozen` means "fail if the lockfile doesn't match pyproject.toml" — this prevents the lock from being silently updated during builds, ensuring reproducible images. `--no-dev` skips development dependencies (test frameworks, linters) to keep the image small.

### .dockerignore

Like `.gitignore` but for Docker builds. Prevents unnecessary files from being sent to the build context:

```
.venv/
__pycache__/
*.py[oc]
.git/
.claude/
```

### Build and run locally

```bash
# Build the image
docker build -t meus-investimentos .

# Run it
docker run -p 8501:8501 -e APP_PASSWORD=mypassword meus-investimentos

# Open http://localhost:8501
```

## Railway deployment

### How Railway works

1. You connect a GitHub repo
2. Railway detects the Dockerfile (or Nixpacks for other setups)
3. On every `git push`, Railway builds the image and deploys it
4. Your app gets a `*.up.railway.app` URL

### Environment variables

Railway injects env vars into the container at runtime. Set them in the Railway dashboard under **Variables**.

For this project:
- `APP_PASSWORD` — the dashboard login password

These are equivalent to `docker run -e APP_PASSWORD=xxx` but managed via Railway's UI.

### Persistent storage caveat

Railway containers are **ephemeral** — the filesystem resets on every deploy. This means:

- PDFs and parsed JSON committed to the repo are available (they're in the Docker image)
- But `data/contributions.json` changes (aportes added via the UI) are **lost on redeploy**

**Solutions:**
1. **Commit contributions.json changes** — push after adding aportes
2. **Railway Volume** — attach persistent storage to `/app/data/`
3. **External database** — move contributions to a database (overkill for now)

**How exactly state is lost:** When you add an aporte via the dashboard UI, it writes to `data/contributions.json` inside the running container's filesystem. This works fine until you `git push` — Railway builds a new Docker image from the repo (which has the old `contributions.json`), starts a new container, and discards the old one. The file changes inside the old container are gone.

For now, option 1 is simplest: after adding aportes in the UI, also update `data/contributions.json` locally and push.

### Railway pricing

- **Trial:** $5 credit (lasts ~2-3 weeks for this app)
- **Hobby plan:** $5/month + usage (more than enough)
- This app uses minimal resources: ~100MB RAM, near-zero CPU when idle

### Railway CLI (optional)

```bash
# Install
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy manually (without git push)
railway up

# View logs
railway logs
```
