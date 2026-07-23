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

## Alternative: deploy to Vercel (password-gated via Edge Middleware)
The repo also ships a Vercel setup so Vercel can auto-deploy on every push. This Vercel deploy is
**password-gated** by `report/dashboard/middleware.js` (Basic Auth, free-plan compatible — see
below), and sends the same hardening headers via `report/dashboard/vercel.json`. The
Cloudflare files (`_worker.js`, `wrangler.jsonc`) and the Vercel file (`vercel.json`) live side by
side in `report/dashboard/`; each platform ignores the other's files (see `.assetsignore`).

- `report/dashboard/vercel.json` marks the project as a plain static site (no build step; `data.js`
  is committed) and sets security headers on every response: `Strict-Transport-Security` (HSTS),
  a same-origin + inline `Content-Security-Policy`, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
- The site is **password-gated** by `report/dashboard/middleware.js`, a Vercel Edge Middleware that
  does HTTP Basic Auth on **every** request before any asset is served. This works on the **free
  Hobby plan** — unlike Vercel's built-in **Deployment Protection**, which requires a paid plan.
  Credentials live only in Vercel environment variables (never in the repo): `SITE_USER` (defaults
  to `nepal`) and `SITE_PASSWORD` (required; the site returns 503 fail-closed if unset). Sign in
  with username = `SITE_USER`, password = `SITE_PASSWORD`.

### Setup (you do this in the Vercel dashboard — I cannot access your account)
The existing project `nepalbikasfund` (https://nepalbikasfund.vercel.app/) can be reused:
1. Project **Settings -> Git -> Connect Git Repository** -> `rayraycodes/NepalDevelopmentFund`
   (your `imregan@umich.edu` account authorises Vercel's GitHub app on the repo).
2. **Settings -> Build & Deployment**: **Root Directory** = `report/dashboard`,
   **Framework Preset** = *Other*, empty Build Command, **Output Directory** = `.`.
   (Vercel auto-detects `middleware.js` at the Root Directory and deploys it as an Edge Function —
   no build step or `package.json` needed.)
3. **Settings -> Environment Variables**: add `SITE_PASSWORD` (the complex password; do not commit
   it) and, optionally, `SITE_USER` (defaults to `nepal`). Apply to Production (and Preview if you
   want previews gated too).
4. Redeploy (**Deployments -> Redeploy**, or push a commit). Visiting the site now prompts for
   credentials: username = `SITE_USER`, password = `SITE_PASSWORD`.

> Pick **one** platform for `main`: if both Cloudflare and Vercel Git integrations stay connected,
> both deploy on every push. Both are now password-gated (Cloudflare via `_worker.js`, Vercel via
> `middleware.js`), but they use **separate** secrets — set `SITE_PASSWORD` in each platform.

## Updating the data
Locally run `make build && make dashboard-data` to regenerate `report/dashboard/data.js` from the
processed CSVs, then commit and push. Cloudflare redeploys automatically.
