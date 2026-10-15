# unnoodle

Hand-picked ComfyUI workflows behind one prompt box, built for phones. You choose image or video, attach inputs and give
each one a role (start frame, reference, edit target and so on), and the request goes to the workflow that fits.

This is the scaffold: the web app runs on mock data and the API only reports its health.

## Layout

- `apps/web`: Next.js (App Router), Tailwind and shadcn/ui. `/` is a placeholder landing page; `/generate` is the app.
- `apps/api`: FastAPI, SQLAlchemy 2, Alembic and Postgres.

## Running it

You need Node 24 with pnpm, uv, and Docker.

```sh
pnpm install
pnpm dev                                # web app on http://localhost:3000

docker compose up -d                    # Postgres on 127.0.0.1:5432
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload    # API on http://localhost:8000; try GET /health
```

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

## Checks

```sh
pnpm lint && pnpm typecheck && pnpm test

pnpm --filter @unnoodle/web exec playwright install chromium   # once
pnpm test:e2e                           # phone viewport, against a production build

cd apps/api
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

API tests that need Postgres are skipped unless `UNNOODLE_TEST_DATABASE_URL` is set, which a `.env` copied from
`.env.example` does. CI runs all of the above on every push and pull request.

## Mock data

`apps/web/src/lib/fixtures.ts` holds the gallery, uploads, projects and composer drafts, typed with the API shapes in
`apps/web/src/lib/types.ts`. `pnpm test` checks that the fixtures follow the rules the API will enforce, such as only
finished generations having outputs. The placeholder images are in `apps/web/public/mock/`.
