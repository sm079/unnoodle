# Hosting

The web app runs on Vercel. Everything else runs in Docker on one machine: Postgres, the API, the worker and the GPU
process, which rents a GPU only while generations wait. The API is reached over HTTPS through Tailscale Funnel or, on a
plain server, Caddy. Vercel passes `/api/*` and `/media/*` through to the API, so the browser still talks to one address
and the sign-in cookie stays first-party. `/` and `/demo` are static, so they work even while that machine is off.

```mermaid
flowchart LR
  B[Browser] --> V[Vercel: Next.js]
  V -- "/api, /media" --> C[Funnel or Caddy]
  subgraph Server [One machine, docker compose]
    C --> A[API] --> P[(Postgres)]
    W[Worker] --> P
    G[GPU process] --> P
    A & W --> M[(media volume)]
  end
  G -- "rents, tunnels, returns" --> R[Renderer on a rented GPU]
  W -- graphs --> R
```

The API image is built from `main` by `.github/workflows/image.yml` and published as `ghcr.io/sm079/unnoodle-api`
(`latest` and `sha-<commit>`). The server only pulls it; nothing is built there.

## The machine

Any machine with Docker and Tailscale can host it, with Funnel giving the API a public HTTPS name. `compose.funnel.yml`
publishes the API on that machine's loopback only (port 18400) and leaves Caddy out:

```sh
cd deploy
cp .env.example .env           # POSTGRES_PASSWORD, the GPU settings; API_HOST is then only for reference
docker compose -f compose.yml -f compose.funnel.yml up -d
tailscale funnel --bg --https=8443 http://127.0.0.1:18400
curl https://<machine>.<tailnet>.ts.net:8443/health
```

The machine name is part of the public address, so name it in the Tailscale admin console first. Funnel opens only that
one port, Postgres isn't published, and the containers run as a non-root user and see only their named volumes, not the
machine's files. Sign-in, media and Generate work only while the machine is on.

### Or: a plain server with Caddy

A small VPS with 1 GB of memory is enough: nothing runs a model on it. Add your SSH key when creating it, then:

```sh
ssh root@<ip>

# 1 GB of swap, for headroom next to Postgres
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

# The image is private while the repository is: a classic GitHub token with only read:packages
docker login ghcr.io -u <github user>

mkdir -p /opt/unnoodle && cd /opt/unnoodle
```

Copy `compose.yml`, `Caddyfile` and `.env.example` from this folder into `/opt/unnoodle`, then:

```sh
cp .env.example .env
nano .env                      # POSTGRES_PASSWORD, and API_HOST: api-<ip with dashes>.sslip.io
docker compose up -d           # migrations run before the API and the worker start
curl https://<API_HOST>/health # {"status":"ok","db":"ok"}
```

sslip.io answers any name that contains an IP address with that address, so there is a public name to get a certificate
for without buying a domain.

## The GPU

With `UNNOODLE_GPU=runpod`, a RunPod API key and a Hugging Face token in `.env`, the `gpu` service rents a GPU when
generations wait, downloads the models one pipeline at a time and tunnels its renderer to `gpu:8288` on the compose
network. It hands the GPU back after 5 idle minutes and stops for the day after 2 hours of GPU time
(`UNNOODLE_GPU_IDLE_STOP_S`, `UNNOODLE_GPU_DAILY_LIMIT_S`). It also deletes stray pods of this app, and each pod deletes
itself if the process stops checking in. Set a spend limit on the RunPod account as well. Admins can stop the GPU from
`/admin`. With `UNNOODLE_GPU=off`, point `UNNOODLE_RENDERER_URL` at a renderer you run yourself.

## The web app

On Vercel, import the repository and set:

- **Root Directory:** `apps/web` (Vercel finds the pnpm workspace above it).
- **Environment variable:** `API_URL=https://<API_HOST>`. `next.config.ts` reads it at build time for the rewrites, so
  redeploy after changing it.

## Data

A new server starts empty. To carry over the accounts, the Demo project and their files from a machine that has them:

```sh
docker compose exec -T postgres pg_dump -U unnoodle -Fc unnoodle > unnoodle.dump   # on that machine
tar -C apps/api/media -czf media.tgz .
scp unnoodle.dump media.tgz root@<ip>:/opt/unnoodle/

# on the server
docker compose stop api worker
docker compose exec -T postgres pg_restore -U unnoodle -d unnoodle --clean --if-exists < unnoodle.dump
docker compose run --rm -T --entrypoint tar api -xzf - -C /data/media < media.tgz
docker compose up -d
docker compose exec api python -m app.previews     # previews for pictures stored before they existed
```

People and credits are managed with the same commands as locally, run inside the API container, for example
`docker compose exec api python -m app.users set-password <email>` or `… python -m app.credits grant <email> 100`.

## Updating

Merging to `main` publishes a new image. On the server (add the `-f` files used to start it):

```sh
docker compose pull && docker compose up -d
```

Or build the image on the machine itself: `docker build -t unnoodle-api:local apps/api`, then set
`API_IMAGE=unnoodle-api:local` in `.env` and `up -d`.

## Known limits

- **Vercel stops a proxied request after 30 seconds.** An upload has to reach the API within that time, so a large clip
  on a slow connection fails. Pictures and short clips are fine.
- The API sees Vercel's address, not the visitor's, so there is still no per-IP limit; the sign-in limit is per email.
- No automatic backups yet: a `pg_dump` and a copy of the media volume are the backup.
