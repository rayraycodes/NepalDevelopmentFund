# Deploying the dashboard (Cloudflare Workers static assets, password-gated)

When the repo was connected to Cloudflare, it was set up as a **Cloudflare Workers project with
static assets** (Cloudflare added `report/dashboard/wrangler.jsonc`). Cloudflare redeploys on every
push to `main`. The site is protected by a single shared password enforced by a Worker
(`report/dashboard/_worker.js`) that runs **before** any asset is served
(`assets.run_worker_first = true`). The password lives only in a Cloudflare secret, never in this
repo. The GitHub repo is **private**.

## How the gate works
`report/dashboard/_worker.js` is the Worker entry (set as `main` in `wrangler.jsonc`). Because
`assets.run_worker_first` is `true`, it runs on every request — including `index.html`, `data.js`
and the charts — checks HTTP Basic Auth against `SITE_PASSWORD` in constant time, and only then
serves the asset via `env.ASSETS.fetch(request)`. No password or hash is shipped to the browser or
stored in the repo, and there is no `*.workers.dev`/asset path that bypasses it. Sign in with
**any username** and **password = `SITE_PASSWORD`**. If `SITE_PASSWORD` is unset the site returns
503 (fail-closed). For per-user (not shared-password) access, use Cloudflare Access instead.

## Security headers + TLS
The Worker sets security headers on **every** response: `Strict-Transport-Security` (HSTS, 1 year),
a `Content-Security-Policy` that allows only same-origin + inline resources (the dashboards load
nothing from third parties), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: no-referrer`, and `Cache-Control: private` on authenticated assets so gated
content is never stored in a shared/CDN cache (the browser still caches per-user, so the ~1 MB of
assets are not re-downloaded each visit). For HSTS to be safe, set the zone's SSL/TLS mode to
**Full (Strict)** and enable **Always Use HTTPS** (SSL/TLS -> Edge Certificates) so there is no
HTTP downgrade path. If you ever add a third-party script/font/CDN, relax `script-src`/`style-src`
in `_worker.js` accordingly.

## Setup (you do this in the Cloudflare dashboard — I cannot access your account)

### 1. Project (already connected)
Workers & Pages -> `nepal-development-fund`. Build output / assets = `report/dashboard` (this is
what `wrangler.jsonc` with `assets.directory: "."` means, since the config lives in that folder).
No build command is needed; `data.js` is committed.

### 2. Set the password (the gate)
Project -> **Settings -> Variables and Secrets** -> add a **Secret**:
- `SITE_PASSWORD` = the complex password (provided separately; do not commit it).
Then redeploy (Deployments -> Retry/redeploy, or just push). Visiting the site now prompts for
credentials: any username, that password.

### 3. Point the custom domain `reganmaharjan.info.np`
Project -> **Settings -> Domains & Routes -> Add -> Custom domain** -> `reganmaharjan.info.np`.
Cloudflare creates the DNS record and TLS automatically (the `info.np` zone must be in your
Cloudflare account, like `com.np`). If a leftover DNS record for that hostname exists, let
Cloudflare replace it.

## Deployment
Cloudflare's native Git integration builds and deploys on every push to `main` — no GitHub Action
is required for publishing. The workflow in `.github/workflows/` is **CI only**: it rebuilds
`data.js` from the committed CSVs and runs the integrity check, so a bad push fails CI. (If you
ever want GitHub Actions to deploy instead, disable Cloudflare's auto-build and use
`wrangler deploy` from `report/dashboard` with a `CLOUDFLARE_API_TOKEN` secret.)

## Alternative: deploy to Vercel (equivalent password gate)
The repo also ships a Vercel setup that reproduces the Cloudflare gate, so Vercel can auto-deploy on
every push with the **same** protection. The Cloudflare files (`_worker.js`, `wrangler.jsonc`) and
the Vercel files (`middleware.js`, `vercel.json`, `package.json`) live side by side in
`report/dashboard/`; each platform ignores the other's files.

- `report/dashboard/middleware.js` is a **Vercel Edge Middleware** — the equivalent of `_worker.js`.
  Its `matcher: "/:path*"` makes it run before every asset (fail-closed like Cloudflare's
  `assets.run_worker_first`), enforces HTTP Basic Auth against `SITE_PASSWORD` in constant time,
  and sets the same security headers (HSTS, CSP, `X-Frame-Options`, `X-Content-Type-Options`,
  `Referrer-Policy`, `Cache-Control`). Any username, password = `SITE_PASSWORD`. If `SITE_PASSWORD`
  is unset it returns 503 (fail-closed). The password lives only in a Vercel env var, never in the repo.
- `report/dashboard/vercel.json` marks the project as a plain static site (no build step; `data.js`
  is committed). `report/dashboard/package.json` pins `@vercel/edge` so the middleware bundles.

### Setup (you do this in the Vercel dashboard — I cannot access your account)
1. Vercel -> **Add New -> Project -> Import** `rayraycodes/NepalDevelopmentFund` (your
   `imregan@umich.edu` account authorises Vercel's GitHub app on the repo).
2. **Root Directory** = `report/dashboard`, **Framework Preset** = *Other*, no build command.
3. **Settings -> Environment Variables** -> add `SITE_PASSWORD` (mark it Sensitive) for every
   environment, then redeploy. Visiting the site now prompts for credentials: any username, that
   password.
4. To use the custom domain on Vercel, move `reganmaharjan.info.np`'s DNS to Vercel
   (**Settings -> Domains**). Vercel provisions TLS automatically.

> Pick **one** platform for `main`: if both Cloudflare and Vercel Git integrations stay connected,
> both deploy on every push. Disconnect the one you are not using (and repoint the domain).

## Updating the data
Locally run `make build && make dashboard-data` to regenerate `report/dashboard/data.js` from the
processed CSVs, then commit and push. Cloudflare redeploys automatically.
