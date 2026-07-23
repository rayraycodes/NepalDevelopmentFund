// Vercel Edge Middleware: HTTP Basic Auth gate for the WHOLE site.
//
// This is the Vercel equivalent of the Cloudflare _worker.js gate. Edge Middleware runs on every
// request BEFORE any static asset is served, so every path (index.html, data.js, the charts) is
// gated. It works on the free Hobby plan, so it does NOT require Vercel's paid Deployment
// Protection.
//
// Credentials are read from environment variables (Project -> Settings -> Environment Variables):
//   SITE_USER      the username (defaults to "nepal" if unset)
//   SITE_PASSWORD  the password (REQUIRED; if unset the site fails closed with 503)
// They are NEVER stored in the repo or sent to the browser.
// To sign in: username = SITE_USER, password = SITE_PASSWORD.

export const config = {
  // Run on everything except Vercel's internal endpoints. Static assets ARE matched, so they are
  // gated too.
  matcher: ["/((?!_vercel|favicon.ico).*)"],
};

export default function middleware(request) {
  const expectedUser = process.env.SITE_USER || "nepal";
  const expectedPass = process.env.SITE_PASSWORD;

  if (!expectedPass) {
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
    const idx = decoded.indexOf(":");
    const user = decoded.slice(0, idx);
    const pass = decoded.slice(idx + 1);
    if (timingSafeEqual(user, expectedUser) && timingSafeEqual(pass, expectedPass)) {
      // Authenticated -> return nothing so the request continues to the static asset. (Every
      // request, cached or not, still passes through this middleware first, so an edge-cached asset
      // is never served to an unauthenticated visitor.)
      return;
    }
  }

  return new Response("Authentication required.", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Nepal Development Funding", charset="UTF-8"',
      "Cache-Control": "no-store",
    },
  });
}

// constant-time comparison to avoid timing side-channels
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
