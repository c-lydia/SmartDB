# SmartDB developer console

This optional React/Vite interface is an API development and integration console.
**The user-facing dashboard is owned by the frontend team.** This console has not been
deployed and is not a replacement for their application.

Run `sh system.sh` from the repository root to start the local Firebase API and console
at `http://127.0.0.1:5000`. The launcher prints local-only administrator credentials.
The [backend integration guide](../cloud/README.md) describes the API, account setup,
device provisioning, command acknowledgements and configuration.

The console exercises login/refresh, device records and credentials, telemetry history,
alerts, notification read state, fused previews and asynchronous control requests.
It stores the current login in browser session storage. No device key is bundled into
the application; provisioning displays a new key once for USB setup.

Build with `npm run build` from the repository root. For UI development while emulators
are running, `npm run dev --workspace dashboard` uses Vite's `/api` proxy to port 5000.
The API contract and implementation do not depend on this console.
