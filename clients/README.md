# Client Scaffolding

Both the web and mobile apps consume the FastAPI backend running at `http://localhost:8000` (or the deployed URL). The shared contract lives in `openapi.json`; regenerate it whenever backend endpoints change:

```bash
curl http://localhost:8000/openapi.json -o clients/openapi.json
```

Use that file for automated type generation (e.g., [`openapi-typescript`](https://www.npmjs.com/package/openapi-typescript) or `orval`).

- `clients/web` – Next.js/React front end.
- `clients/mobile` – Expo/React Native app.

Each directory contains setup notes plus a lightweight API helper showcasing how to call `POST /visa-pack`.
