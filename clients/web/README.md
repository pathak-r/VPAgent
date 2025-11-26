# Web Client (Next.js)

The `visa-pack-web` folder is a ready-to-run Next.js + Tailwind project with a single page form that calls the FastAPI backend. Travellers pick destinations via region-grouped selectors, assign nights per country, and the UI auto-computes the trip’s end date plus the primary/first-entry country when ties occur.

## Run locally

```bash
cd clients/web/visa-pack-web
npm install # already executed during scaffolding, but safe to rerun
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local # adjust for deployments
npm run dev
```

With the backend running (`uvicorn vp_generator.api:app --reload`), open `http://localhost:3000` and submit the form to generate a visa pack.

## Customization pointers

- Update `src/app/page.tsx` to add new inputs (e.g., first country of entry) or richer preview sections.
- `src/lib/api.ts` contains the thin fetch wrapper that targets `POST /visa-pack`.
- If you export `openapi.json`, you can generate TypeScript types and replace the hand-written interfaces with generated ones (`npx openapi-typescript ../../openapi.json -o src/lib/api-types.ts`).
