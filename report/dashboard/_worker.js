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
        return env.ASSETS.fetch(request); // authenticated -> serve the static asset
      }
    }

    return new Response("Authentication required.", {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="Nepal Development Funding", charset="UTF-8"',
        "Cache-Control": "no-store",
      },
    });
  },
};

// constant-time comparison to avoid timing side-channels
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
