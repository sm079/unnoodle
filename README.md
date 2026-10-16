# unnoodle

AI pictures and videos from one prompt box, built for phones. Node-based generation tools hand you every setting and
a canvas of wires to connect; unnoodle keeps the pipelines on the server and leaves you a few plain choices. You choose
a picture or a video, describe it and attach any photos or clips to work from, and the request goes to the pipeline that
fits: a prompt alone makes a picture (Krea 2) or a video (MiniMax H3), a photo to edit goes to FLUX.2 Klein, and photos
or clips attached to a video are its references. Settings are in plain words: a quality, a shape and, for videos, a
length.

The web app sends requests to the API, which queues them in Postgres; a worker builds each request's graph, runs it on
a GPU render server (the renderer) and stores what it makes.

## Layout

- `apps/web`: Next.js (App Router), Tailwind and shadcn/ui. `/` is the landing page for people who are signed out (signed-in visitors go to `/generate`, the app). Its pictures and videos are copies of Demo outputs in `apps/web/public/showcase`.
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
uv run python -m app.worker             # runs queued generations on the renderer (below)
```

The API queues generations in Postgres and the worker, a separate process, runs them on the renderer one at a time. Several
workers can share the queue. It is first in, first out unless Smart Queue is on (a switch in the sidebar, for admins,
since it reorders everyone's jobs): then each generation's estimated run time moves it back, by 10 minutes at most, so
quick ones go ahead of long videos.

The browser only talks to the web app, which passes `/api/*` and `/media/*` through to the API (`API_URL`, by default
`http://127.0.0.1:8000`), so a phone needs one address and no cross-origin setup.

Every setting has a working default. To change one, copy `.env.example` to `.env`; compose and the API both read it.

### Accounts

People sign up on `/sign-up` with an email and a password, and everything they upload, generate or file in a project
is theirs alone: the API filters every query by owner, answers 404 for anyone else's things, and serves `/media` files
only to their owner. A signed-in browser holds a random token in an httpOnly, SameSite=Lax cookie; the database keeps
only its SHA-256, and passwords are hashed with Argon2. After 5 wrong passwords for one email in 15 minutes, signing in to it is refused until the
oldest ages out; a right password clears the count. Set `UNNOODLE_SECURE_COOKIES=true` wherever the app is served
over HTTPS, the tailnet address included.

There's no email yet, so the first admin and forgotten passwords go through the command line (run from `apps/api`):

```sh
uv run python -m app.users create you@example.com --admin
uv run python -m app.users set-password you@example.com   # also signs the account out everywhere
uv run python -m app.users admin someone@example.com      # --remove to undo
```

Whatever was made before there were accounts belongs to `owner@unnoodle.local`, an admin with no password until one is
set this way.

A demo project is shown to every account, so a new one has something to look at before making anything: its
generations, their inputs and outputs, which anyone can use as inputs. Only its owner adds to it.
`uv run python -m app.demo krea2-turbo flux2-klein-edit minimax-h3` files every finished generation of those pipelines
into one called Demo.

### Credits

Generating costs credits; there's no payment. New accounts start with none and can look around with Generate turned
off until they redeem an invite code or an admin grants some. Prices are fixed and shown on Generate:

| Request                     | Credits                                      |
| --------------------------- | -------------------------------------------- |
| A picture                   | 1, or 2 at high quality                      |
| A video, for each 5 seconds | 10 low, 20 medium, 40 high                   |
| Each clip attached to video | 10 more (the model works through its frames) |

"How many" queues that many, each charged in full. Every credit given or taken is a row in an append-only ledger
(`credit_entries`), so a balance is a sum and every change can be traced. Queuing charges at once, under a lock on the
account so two requests can't spend the same credits; a generation that fails gets its credits back in the same
transaction that marks it failed. Each person can have 8 generations waiting or running at once.

```sh
uv run python -m app.credits invite WELCOME --credits 50 --uses 20 --days 14
uv run python -m app.credits grant someone@example.com 100 --note "for the demo"   # negative takes back
uv run python -m app.credits balance someone@example.com
```

### Safety and the admin page

Prompts containing a banned word or phrase are refused before anything is charged, with the word named so the person
can say it another way. Words are compared after evening out capitals, accents, digits and symbols standing in for
letters (`nud3`, `$ex`), held-down letters, spaced-out letters and plurals. A new install starts with a short list.

This is a first layer only, and it is meant for a small invite-only app: misspellings, other languages and what is in
an uploaded photo get past a word list, and photo edits of real people are the bigger risk. The other layers are that
generating takes credits, which only admins hand out, and that admins see everything.

`/admin` (admins only; linked from the sidebar) lists everyone's generations with who made them and deletes any of
them, with its outputs, their files and the uploads nothing else uses. It also gives credits, makes invite codes and
shows their uses, and keeps the banned words.

### The renderer without models

The renderer is a node-graph inference server: it takes a graph as JSON over HTTP, reports progress over a websocket
and serves the files it writes (`app/worker/renderer.py` makes every call). To develop without downloading any models,
start one (0.39 or later) from the repo root with `dev/renderer` as its base directory:

```sh
python <path-to-renderer>/main.py --base-directory dev/renderer --port 8189 --cpu --disable-auto-launch
```

It then loads only the development node in `dev/renderer/custom_nodes`, and keeps its inputs, outputs and settings in
`dev/renderer` (git-ignored), so an existing renderer install is left as it was. The node stands in for a model: it
takes as long as the real model would on an RTX 5090 (a set-up with no progress, then steps), tints each image by the
seed and writes the prompt on it. It fails like a GPU out of memory when the prompt contains `#oom`, and finishes in a
few seconds when it contains `#quick`. Port 8189 keeps it clear of a normal renderer on 8188.

Pipelines are code: each one builds its graph for every request, with one image chain per attached photo
(`app/pipelines.py` describes the contract). `app/catalogues/dev.py` holds stand-ins that run on this renderer, and
`app/catalogues/real.py` the ones that need models. `UNNOODLE_PIPELINES` picks the catalogue (`dev` unless set).

### On a phone

```sh
pnpm serve                              # everything, with a production build on http://127.0.0.1:18300
```

`pnpm serve` starts Postgres with docker compose if nothing answers yet, applies the migrations, then runs the API, the
worker and a production build of the web app (`next build`, then `next start`), each line of output prefixed with the
process it came from. It uses a renderer that already answers at `UNNOODLE_RENDERER_URL`; otherwise it starts the dev one
when `UNNOODLE_DEV_RENDERER_MAIN` (and, for a portable build, `UNNOODLE_DEV_RENDERER_PYTHON`) says where it is. If any
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
`.env.example` does. They use their own database, which they create and migrate. The few that talk to a real renderer
also need the dev renderer running and `UNNOODLE_TEST_RENDERER_URL` set. CI runs all of the above on every push and pull
request, apart from the renderer tests.

## Mock data

`apps/web/src/lib/fixtures.ts` holds the gallery, uploads, projects and composer drafts, typed with the API shapes in
`apps/web/src/lib/types.ts`. `pnpm test` checks that the fixtures follow the rules the API will enforce, such as only
finished generations having outputs. The placeholder images are in `apps/web/public/mock/`.
