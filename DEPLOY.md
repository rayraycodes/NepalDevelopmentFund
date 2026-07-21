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

## Alternative: deploy to Vercel (public, no password)
The repo also ships a Vercel setup so Vercel can auto-deploy on every push. Unlike the Cloudflare
project, this Vercel deploy is **public** — there is no password gate (that would need a paid plan or
custom auth). It still sends the same hardening headers via `report/dashboard/vercel.json`. The
Cloudflare files (`_worker.js`, `wrangler.jsonc`) and the Vercel file (`vercel.json`) live side by
side in `report/dashboard/`; each platform ignores the other's files (see `.assetsignore`).

- `report/dashboard/vercel.json` marks the project as a plain static site (no build step; `data.js`
  is committed) and sets security headers on every response: `Strict-Transport-Security` (HSTS),
  a same-origin + inline `Content-Security-Policy`, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
- There is no `SITE_PASSWORD` and no Edge Middleware: anyone with the URL can view the dashboard.
  If you later want to gate it, use Vercel's built-in **Deployment Protection** (paid) or add a
  Basic-Auth Edge Middleware.

### Setup (you do this in the Vercel dashboard — I cannot access your account)
The existing project `nepalbikasfund` (https://nepalbikasfund.vercel.app/) can be reused:
1. Project **Settings -> Git -> Connect Git Repository** -> `rayraycodes/NepalDevelopmentFund`
   (your `imregan@umich.edu` account authorises Vercel's GitHub app on the repo).
2. **Settings -> Build & Deployment**: **Root Directory** = `report/dashboard`,
   **Framework Preset** = *Other*, empty Build Command, **Output Directory** = `.`.
3. Redeploy (**Deployments -> Redeploy**, or push a commit). The site is live and public.

> Pick **one** platform for `main`: if both Cloudflare and Vercel Git integrations stay connected,
> both deploy on every push. Note Cloudflare's site is password-gated while this Vercel deploy is
> public, so don't expose data on Vercel that must stay behind the Cloudflare gate.

## Updating the data
Locally run `make build && make dashboard-data` to regenerate `report/dashboard/data.js` from the
processed CSVs, then commit and push. Cloudflare redeploys automatically.
