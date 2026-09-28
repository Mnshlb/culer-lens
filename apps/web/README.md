# Culer Lens: web app

Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui, with SVG pitch graphics, Recharts, Motion and
TanStack Query. It reads everything from the FastAPI service in `apps/api`.

```bash
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

| Script | What it does |
|---|---|
| `npm run dev` / `build` / `start` | Next.js development server, production build, production server |
| `npm run lint` / `typecheck` | ESLint; route type generation (`next typegen`) and `tsc --noEmit` |
| `npm run test:e2e` | Playwright end-to-end tests (desktop and mobile) against the production build |
| `npm run api:types` | Regenerate `src/lib/api-schema.d.ts` from the running API's OpenAPI schema |

The end-to-end tests do not need the data or a running API: every API call is served from
`e2e/fixtures/api.json`, which is generated from a synthetic database by `scripts/export_e2e_fixtures.py`.

## Structure

```
src/app/            routes: overview, matches, matches/[id], players, players/[id], model, about
src/components/     pitch/ (SVG pitch, heatmaps, shot map, pass network, lineup), charts/, match/, player/, model/
src/lib/            typed API client and hooks, generated OpenAPI types, formatting, colour tokens
```

Chart colours are defined once in `src/app/globals.css` and `src/lib/theme.ts`: garnet, blue and gold for
categories (checked for colour-vision deficiency and contrast on the dark surfaces), and green / grey / red for
win / draw / loss, always shown together with the W/D/L letter.
