// Vercel Edge Middleware — password gate for the WHOLE site.
// This is the Vercel equivalent of the Cloudflare Worker in _worker.js: with the matcher below it
// runs before any static asset is served, so every path (index.html, data.js, the charts, the
// vendored ECharts, everything under /usforeignaiddata) is gated. Keep the two in sync.
//
// The password is read from the SITE_PASSWORD environment variable (Vercel -> Project ->
// Settings -> Environment Variables; add it as a Sensitive/Secret value for every environment).
// It is NEVER stored in the repo or sent to the browser.
// Fail-closed: if SITE_PASSWORD is unset, everything is denied.
// To sign in: any username, password = SITE_PASSWORD.

import { next } from "@vercel/edge";

// Run on every request. `.*` also matches the root; nothing is excluded, so the gate is fail-closed
// exactly like Cloudflare's assets.run_worker_first = true.
export const config = {
  matcher: "/:path*",
};

export default function middleware(request) {
  const expected = process.env.SITE_PASSWORD;
  if (!expected) {
    return harden(new Response("Site password is not configured.", { status: 503 }), "no-store");
  }

  const header = request.headers.get("Authorization") || "";
  if (header.startsWith("Basic ")) {
    let decoded = "";
    try {
      decoded = atob(header.slice(6));
    } catch (_) {
      decoded = "";
    }
    const password = decoded.slice(decoded.indexOf(":") + 1);
    if (timingSafeEqual(password, expected)) {
      // authenticated -> continue to the static asset, with security headers. Cache-Control:private
      // keeps gated content out of any SHARED/CDN cache (no leak) while still letting the viewer's
      // own browser reuse the bytes (no-cache = revalidate, so the ~1 MB of assets are not
      // re-downloaded every visit).
      return harden(next(), "private, no-cache");
    }
  }

  return harden(
    new Response("Authentication required.", {
      status: 401,
      headers: { "WWW-Authenticate": 'Basic realm="Nepal Development Funding", charset="UTF-8"' },
    }),
    "no-store",
  );
}

// Security headers on every response. CSP allows only same-origin + inline (the dashboards use
// inline <script>/<style>/onclick and a vendored ECharts; they load NOTHING from third parties),
// and forbids framing/downgrade. Relax script-src if a future CDN dependency is added.
// Headers are mutated in place so the `next()` continuation signal is preserved.
function harden(resp, cacheControl) {
  const h = resp.headers;
  h.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload");
  h.set("X-Frame-Options", "DENY");
  h.set("X-Content-Type-Options", "nosniff");
  h.set("Referrer-Policy", "no-referrer");
  h.set("Cache-Control", cacheControl);
  h.set(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; " +
      "base-uri 'self'; form-action 'self'",
  );
  return resp;
}

// constant-time comparison to avoid timing side-channels
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
