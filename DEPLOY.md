# Deploying the dashboard (Cloudflare Pages, password-gated)

The dashboard (`report/dashboard/`) is published to **Cloudflare Pages** and protected by a
single shared password enforced at the edge by a Pages Function
(`report/dashboard/functions/_middleware.js`). The password lives only in a Cloudflare secret,
never in this repo. The GitHub repo is **private**.

## One-time setup (you do this in Cloudflare + GitHub — I cannot access your accounts)

### 1. Create the Cloudflare Pages project
- Cloudflare dashboard -> Workers & Pages -> Create -> Pages -> **Connect to Git** ->
  pick `rayraycodes/NepalDevelopmentFund`.
- Build settings: **Framework preset = None**, **Build command =** (leave empty),
  **Build output directory = `report/dashboard`**.
- Name the project **`nepal-development-fund`** (must match `--project-name` in
  `.github/workflows/deploy.yml`, or edit that line).
- (If you prefer the GitHub Actions workflow to deploy instead of Cloudflare's native Git build,
  you can disable automatic builds on the Pages project and rely on the Action below.)

### 2. Set the page password (the gate)
- Pages project -> Settings -> **Environment variables** -> Production -> add:
  - `SITE_PASSWORD` = the complex password (provided separately; do not commit it).
- Redeploy. Visiting the site now prompts for credentials: **any username, password =
  `SITE_PASSWORD`**. If `SITE_PASSWORD` is unset the site returns 503 (fail-closed).

### 3. Point the custom domain `reganmaharjan.info.np`
- Make sure the `info.np` zone (or `reganmaharjan.info.np`) is in your Cloudflare account
  (same as `reganmaharjan.com.np`).
- Pages project -> **Custom domains** -> Set up a custom domain -> `reganmaharjan.info.np`.
- Cloudflare auto-creates the CNAME and provisions TLS. (Because the domain is already on
  Cloudflare, no manual DNS record is needed; if it asks, accept the CNAME it proposes.)

### 4. (Optional) GitHub Actions deploy
If you want pushes to deploy via GitHub Actions (instead of Cloudflare's native Git build),
add these **GitHub repo secrets** (Settings -> Secrets and variables -> Actions):
- `CLOUDFLARE_API_TOKEN` — a token with the **Cloudflare Pages: Edit** permission.
- `CLOUDFLARE_ACCOUNT_ID` — your account id (Cloudflare dashboard URL or Workers & Pages overview).
The workflow `.github/workflows/deploy.yml` rebuilds `data.js` and runs `wrangler pages deploy`.

## How the gate works
`functions/_middleware.js` runs on every request at the edge, before any asset is served. It
requires HTTP Basic Auth and compares the supplied password to `SITE_PASSWORD` in constant time.
No password or hash is shipped to the browser or stored in the repo, so this is a real gate (not
client-side theater). It is a single shared password; for per-user access use Cloudflare Access
instead.

## Updating the data
Locally: `make all` (or at least `make build && make dashboard-data`) regenerates
`report/dashboard/data.js` from the processed CSVs, then commit. The deploy refreshes the page.
