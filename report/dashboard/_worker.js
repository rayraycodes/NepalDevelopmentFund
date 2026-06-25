// Cloudflare Worker entry for the static-assets project (see wrangler.jsonc).
// Password gate for the WHOLE site. With assets.run_worker_first = true, this Worker runs before
// any asset is served, so every path (including index.html, data.js, the charts) is gated.
//
// The password is read from the SITE_PASSWORD secret (Workers & Pages -> the project ->
// Settings -> Variables and Secrets). It is NEVER stored in the repo or sent to the browser.
// Fail-closed: if SITE_PASSWORD is unset, everything is denied.
// To sign in: any username, password = SITE_PASSWORD.

export default {
  async fetch(request, env) {
    const expected = env.SITE_PASSWORD;
    if (!expected) {
      return new Response("Site password is not configured.", { status: 503 });
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
        // authenticated -> serve the static asset, with security headers. Cache-Control:private
        // keeps gated content out of any SHARED/CDN cache (no leak) while still letting the
        // viewer's own browser reuse the bytes (no-cache = revalidate via ETag, so the 1 MB of
        // assets are not re-downloaded every visit).
        const asset = await env.ASSETS.fetch(request);
        return harden(asset, "private, no-cache");
      }
    }

    return harden(
      new Response("Authentication required.", {
        status: 401,
        headers: { "WWW-Authenticate": 'Basic realm="Nepal Development Funding", charset="UTF-8"' },
      }),
      "no-store",
    );
  },
};

// Security headers on every response. CSP allows only same-origin + inline (the dashboards use
// inline <script>/<style>/onclick and a vendored ECharts; they load NOTHING from third parties),
// and forbids framing/downgrade. Relax script-src if a future CDN dependency is added.
function harden(resp, cacheControl) {
  const h = new Headers(resp.headers);
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
  return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: h });
}

// constant-time comparison to avoid timing side-channels
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
