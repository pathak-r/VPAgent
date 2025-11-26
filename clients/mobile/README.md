# Mobile Client (Expo)

1. `cd clients/mobile && npx create-expo-app@latest visa-pack-mobile`
2. Inside the new app install deps:
   ```bash
   cd visa-pack-mobile
   npm install expo-constants
   npm install --save-dev openapi-typescript
   npx openapi-typescript ../openapi.json -o src/lib/api-types.ts
   ```
3. Drop `api.ts` (from this folder) into `src/lib/api.ts` and update the base URL to point at your deployed backend or LAN IP (Expo requires `http://<machine-ip>:8000`).
4. Build a form screen that gathers the same `TripRequestPayload` fields and calls `createVisaPack`.

During development run:

- Backend: `uvicorn vp_generator.api:app --reload --host 0.0.0.0`
- Expo dev server: `npx expo start`

Remember to expose the machine IP/port to the device/simulator via Expo’s connection screen.
