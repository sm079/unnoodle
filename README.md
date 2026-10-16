# unnoodle

Hand-picked ComfyUI workflows behind one prompt box, built for phones. You choose a picture or a video, describe it and
attach any photos or clips to work from, and the request goes to the workflow that fits: a prompt alone makes a picture
(Krea 2) or a video (MiniMax H3), a photo to edit goes to FLUX.2 Klein, and photos or clips attached to a video are its
references. Settings are in plain words: a quality, a shape and, for videos, a length.

The web app sends requests to the API, which queues them in Postgres; a worker runs each one on ComfyUI and stores what
it makes.

## Layout

- `apps/web`: Next.js (App Router), Tailwind and shadcn/ui. `/` is a placeholder landing page; `/generate` is the app.
- `apps/api`: FastAPI, SQLAlchemy 2, Alembic and Postgres.

## Running it

You need Node 24 with pnpm, uv, and Docker, and for videos ffmpeg (with ffprobe) on the PATH: the API uses it to cut
uploaded clips to what the video model uses and to make a still of each video.

```sh
pnpm install
pnpm dev                                # web app on http://localhost:3000

docker compose up -d                    # Postgres on 127.0.0.1:5432
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload    # API on http://localhost:8000; try GET /health
uv run python -m app.worker             # runs queued generations on ComfyUI (below)
```

The API queues generations in Postgres and the worker, a separate process, runs them on ComfyUI one at a time. Several
workers can share the queue. It is first in, first out unless Smart Queue is on (a switch in the sidebar): then each
generation's estimated run time moves it back, by 10 minutes at most, so quick ones go ahead of long videos.

The browser only talks to the web app, which passes `/api/*` and `/media/*` through to the API (`API_URL`, by default
`http://127.0.0.1:8000`), so a phone needs one address and no cross-origin setup.

Every setting has a working default. To change one, copy `.env.example` to `.env`; compose and the API both read it.

### ComfyUI without models

Generations run on ComfyUI. To develop without downloading any models, start ComfyUI (0.39 or later) from the repo
root with `dev/comfyui` as its base directory:

```sh
python <path-to-ComfyUI>/main.py --base-directory dev/comfyui --port 8189 --cpu --disable-auto-launch
```

It then loads only the development node in `dev/comfyui/custom_nodes`, and keeps its inputs, outputs and settings in
`dev/comfyui` (git-ignored), so an existing ComfyUI install is left as it was. The node stands in for a model: it
reports progress step by step, tints each image by the seed and writes the prompt on it, and fails like a GPU out of
memory when the prompt contains `#oom`. Port 8189 keeps it clear of a normal ComfyUI on 8188.

Workflows are code: each one builds its ComfyUI graph for every request, with one image chain per attached photo
(`app/workflows.py` describes the contract). `app/catalogues/dev.py` holds stand-ins that run on this ComfyUI, and
`app/catalogues/real.py` the ones that need models. `UNNOODLE_WORKFLOWS` picks the catalogue (`dev` unless set).

### On a phone

```sh
pnpm serve                              # everything, with a production build on http://127.0.0.1:18300
```

`pnpm serve` starts Postgres with docker compose if nothing answers yet, applies the migrations, then runs the API, the
worker and a production build of the web app (`next build`, then `next start`), each line of output prefixed with the
process it came from. It uses a ComfyUI that already answers at `UNNOODLE_COMFYUI_URL`; otherwise it starts the dev one
when `UNNOODLE_DEV_COMFYUI_MAIN` (and, for a portable build, `UNNOODLE_DEV_COMFYUI_PYTHON`) says where it is. If any
of them stops, it stops the rest, and Ctrl+C stops them all. A phone gets the production build rather than `next dev`,
which only serves its scripts to `localhost` and is slow over a network.

The web app listens on 127.0.0.1 only, and the phone reaches it through [Tailscale](https://tailscale.com). With this
machine and the phone signed in to the same tailnet, run once:

```sh
tailscale serve --bg 18300
```

Tailscale then forwards `https://<machine>.<tailnet>.ts.net` to the web app, for devices on the tailnet only, and
`pnpm serve` prints that address once it is up. Tailscale terminates HTTPS with a real certificate, so the phone gets
a secure context, which browser APIs such as `crypto.randomUUID` need, and no firewall port is opened. The first time,
`tailscale serve` asks you to enable HTTPS for the tailnet; certificates are public, so the machine and tailnet names
end up in Certificate Transparency logs.

`pnpm test:e2e` builds into the same `.next` directory, so restart `pnpm serve` after running it.

## Checks

```sh
pnpm lint && pnpm typecheck && pnpm test

pnpm --filter @unnoodle/web exec playwright install chromium   # once
pnpm test:e2e                           # phone viewport, against a production build

cd apps/api
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

API tests that need Postgres are skipped unless `UNNOODLE_TEST_DATABASE_URL` is set, which a `.env` copied from
`.env.example` does. They use their own database, which they create and migrate. The few that talk to a real ComfyUI
also need the dev ComfyUI running and `UNNOODLE_TEST_COMFYUI_URL` set. CI runs all of the above on every push and pull
request, apart from the ComfyUI tests.

## Mock data

`apps/web/src/lib/fixtures.ts` holds the gallery, uploads, projects and composer drafts, typed with the API shapes in
`apps/web/src/lib/types.ts`. `pnpm test` checks that the fixtures follow the rules the API will enforce, such as only
finished generations having outputs. The placeholder images are in `apps/web/public/mock/`.
