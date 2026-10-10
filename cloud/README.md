# SmartDB Firebase API and team integration

The implemented v2 bench system consists of the two [ESP-IDF firmware targets](../esp_idf/smartdb_fusion/README.md)
and this Firebase Auth / Firestore / Cloud Functions HTTP API. **The user dashboard belongs
to the frontend team.** The optional [developer console](../dashboard/README.md) exercises
the API locally; it is not the product UI and has not been deployed.

The separate [Python CoAP gateway](../backend/README.md) remains available. This HTTPS path
does not implement its production CoAP/DTLS transport or a trained AI inference service.

## Run locally

Install Node.js 22 LTS with npm and Java 21 or newer, then from the repository root run:

```sh
sh system.sh
```

The launcher installs the locked dependencies when missing, builds the developer console,
starts Firebase emulators, and creates a local administrator. It prints the credentials and
saves them in `.local/admin.json` with owner-only permissions. No Firebase account or cloud
project is needed. Open `http://127.0.0.1:5000`; the API base URL is
`http://127.0.0.1:5000/api/v1`. Emulator inspection is at `http://127.0.0.1:4000`.
Keep these development services on loopback. Ctrl+C exports local data into `.local/firebase`
for the next run. `.local/` is ignored by Git and is excluded from documentation exports.

`sh system.sh firmware` opens the existing two-board setup menu. Stop the local services
before `sh system.sh test`, which uses fresh, disposable Auth/Firestore emulators. Tests
never import or alter the saved `.local/firebase` data.

## Frontend handoff

Import the [OpenAPI contract](../postman/specs/smartdb_api/openapi.yaml) and use the
[Postman collection and environment](../postman/documents/README.md). All routes below
are relative to `/api/v1`.

1. Sign in with `POST /auth/login` using an already-provisioned email/password account.
   Send the returned `access_token` as a bearer token. On expiry, call `/auth/refresh`
   with the opaque `refresh_token`; replace both tokens. Refresh tokens rotate once.
   `/auth/logout` revokes the supplied application session. Raw Firebase SDK tokens
   obtained outside this login flow do not automatically create an API session.
2. Use `GET /devices`, then the selected device's `/status`, `/telemetry/latest`,
   `/telemetry?limit=100`, `/config` and `/commands`. Latest telemetry returns 404 before
   the first upload. History is newest **server receipt** first; `from`/`to` filter that
   receipt time because a board may lack a synchronized clock. The API currently returns
   bounded lists, not cursor pagination.
3. Display unavailable readings as unknown: voltage and power are null on v2. Preserve
   `synthetic`, sensor validity and `vision.ready`. Device `online` means contact within
   180 seconds, **not** that any sensor reading is currently fresh. Telemetry can contain
   delayed queued samples. Local fusion freshness applies at capture, not at browser view.
4. Fetch `/devices/{id}/fusion/frame` with the bearer header and render a blob URL.
   `X-Received-At`, `X-Fusion-Sequence`, `X-Capture-Age-Ms`, and `X-Synthetic` describe the
   stored preview. Label its age; it is not live video and may outlive device connectivity.
   Only one 320 × 240 BMP is retained per device. Numerical temperatures come from native
   MLX samples in telemetry, not interpolated image colors.
5. Use `/alerts` and `/notifications` for in-app events. Resolving an alert changes only
   the record. It never re-arms the relay. Email, SMS and push delivery are not implemented.
6. Treat configuration and commands as asynchronous. `PUT /devices/{id}/config` records
   desired limits and queues `APPLY_CONFIG`; inspect `/commands` for success/failure.
   A 200/202 response is not evidence the board acted. There is no remote close/re-arm.

The same-origin console needs no CORS configuration. For a separately hosted team UI,
set `SMARTDB_ALLOWED_ORIGINS` to an explicit comma-separated list of origins, including
scheme and port. For local emulators, place it in `cloud/.env.local`, for example
`SMARTDB_ALLOWED_ORIGINS=http://localhost:5173`. Alternatively proxy `/api` through your
frontend's development server. Cross-origin requests still require bearer authentication;
no wildcard origin or cross-site cookie authentication is enabled.

## Ownership and device installation

Records are owner-scoped, including for administrators. Operators can create their own
device records, upload diagnostics, update desired limits and request commands; viewers
cannot write operational data. Administrators can list account profiles and provision or
rotate credentials **for their own devices**. Shared households and device ownership
transfer are not implemented. A viewer needs a device record assigned to their UID by
the project administrator before it can see that installation.

Create a device with `POST /devices`, then provision it with `POST /device/register`
using `device_id`, `serial_number`, `hardware` and `firmware`. The response contains a
one-time `device_key`; the server stores only its SHA-256 lookup hash. A device credential
can access only that board and cannot manage accounts or issue control commands. If lost,
an owner administrator can call `/devices/{id}/credential/rotate`; the old key stops working
immediately. Keep keys out of frontend bundles, logs and committed Postman environments.

In the S3 setup menu, enter the deployed **HTTPS** URL ending in
`/api/v1/devices/DEVICE_ID/telemetry` and the device key as `telemetry_token`, then save and
restart. The camera receives only its separate local token. Physical boards cannot reach
the computer's loopback address, and the firmware intentionally rejects plain HTTP upload
URLs. The emulator is for software integration; use a reachable HTTPS deployment for boards.

## Delivery, configuration and commands

Telemetry is acknowledged with 202 only after Firestore persistence. `sample_id` is unique
within a device; identical retries return `duplicate: true`, conflicting content returns 409.
Without `sample_id`, each legacy diagnostic upload is a new record. Non-synthetic transitions
into a tripped state create an alert and in-app notification in the same transaction.

The 202 body carries at most one pending command, delivered only with a device credential:

| Command | Behavior |
|---|---|
| `OPEN_RELAY` | Requests local opening; physical re-arm is required |
| `REQUEST_STATUS` | Wakes the telemetry collector |
| `SET_INTERVAL` | Persists a 5–60 second telemetry interval; does not change sensor sampling |
| `APPLY_CONFIG` | Generated by config PUT; applies 20–100°C, >0–1 A and 5–60 s bounds, opens relay |

Local commissioning and CT calibration are preserved during cloud configuration. A board
acknowledges `/commands/{id}/ack` with `success` or `failed` and an ESP-IDF error name.
An OPEN_RELAY acknowledgement means the request was accepted by firmware; check subsequent
relay telemetry for reported output state. It is not contact-position feedback.

Commands expire for delivery after two minutes; GET returns the last 100 records for users
or the oldest available pending command for a device. The board persists its last command
ID/result and interval, making an ordinary retry/reboot idempotent. A power failure between
applying configuration and recording its command can cause safe reapplication. Do not reset
the server command counter for an already-paired board: IDs must keep increasing.
For a replacement cloud project, reprovision/reset the board's cloud-control NVS namespace
as part of maintenance. The board never accepts a remote close command.

The S3 sends a best-effort fresh preview after a successful telemetry upload, at most once
per 30 seconds (up to the configured telemetry interval when longer). Failed previews are
dropped; stale images are never queued for retry. The server validates the fixed BMP layout,
limits uploads to six per minute, and stores the latest frame below Firestore's document
size limit. JSON requests are limited to 32 KiB, and API actor rate limits apply.

## Firebase deployment

The repository is configured but **no live Firebase project has been deployed**.

1. Create/select a Firebase project, enable Email/Password Authentication and create the
   default Firestore database. Cloud Functions deployment requires a billing-enabled
   [Blaze project](https://firebase.google.com/docs/hosting/functions). Use a region near
   the installed devices; the checked-in function region is `asia-southeast1`.
2. Copy `cloud/.env.example` to `cloud/.env.YOUR_PROJECT_ID`, set the Firebase web API key
   and any team frontend origins. Keep the file private. Login/refresh follow the
   [Firebase Auth REST interface](https://firebase.google.com/docs/reference/rest/auth).
3. Create the initial account in Firebase Authentication. With authorized Google application
   default credentials on the administrator machine, provision its application profile:

   ```sh
   node cloud/scripts/provision-user.mjs --project YOUR_PROJECT_ID --email admin@example.com --name Administrator --role admin
   ```

   This only provisions an existing Firebase account; it does not accept a password on the
   command line or silently change an existing role.
4. Deploy the API and deny-by-default Firestore rules using Firebase CLI:

   ```sh
   npx firebase login
   npx firebase deploy --project YOUR_PROJECT_ID --only functions,firestore
   ```

   A function URL has the form `https://asia-southeast1-YOUR_PROJECT_ID.cloudfunctions.net/api`;
   append `/api/v1` for the API base. The `api` function name and `/api/v1` route prefix are
   separate. Configure the team's frontend origin or its reverse proxy accordingly.
   The checked-in Hosting configuration is for the optional developer console; deploying
   `functions,firestore` does not publish it or replace the team's user dashboard.

Firestore clients cannot read the database directly; the API uses Admin SDK credentials and
enforces ownership/roles. Telemetry and alerts are retained until administratively removed;
production retention, backups, session cleanup, monitoring and billing budgets must be
configured for the chosen deployment. This bench implementation has no trained anomaly
model, OTA updater, production DTLS path or external notification delivery.

## Source and verification

| File | Responsibility |
|---|---|
| [src/app.js](src/app.js) | Routes, durable telemetry/alerts, configuration commands, bounded previews |
| [src/security.js](src/security.js) | Firebase login, session rotation, owner/role checks, device keys and rate limits |
| [src/schemas.js](src/schemas.js) | Strict request validation and bench limits |
| [src/index.js](src/index.js) | Cloud Functions deployment entry point |
| [test/api.test.js](test/api.test.js) | Emulator integration tests for persistence, permissions and retries |

Run `npm test` from the repository root. Firmware verification remains
`sh tools/check.sh` inside `esp_idf/smartdb_fusion`, plus PlatformIO target builds.
Software tests do not establish sensor accuracy, power capacity or physical relay behavior.
