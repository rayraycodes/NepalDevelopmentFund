// Cloudflare Pages Function — HTTP Basic Auth gate for the whole site.
//
// IMPORTANT (Cloudflare requirement): the /functions directory must live at the ROOT of the
// Pages project, NOT inside the build output / static root (report/dashboard). With the Git
// integration and a build output directory of report/dashboard, Cloudflare reads Functions from
// here (the repo root). This file is what actually gates the deployed site.
//
// The password is read from the SITE_PASSWORD environment secret configured in the Cloudflare
// Pages project (Settings -> Environment variables). It is NEVER stored in the repo or sent to
// the browser. Fail-closed: if SITE_PASSWORD is unset, everything is denied.
// To sign in: any username, password = SITE_PASSWORD.

export async function onRequest(context) {
  const { request, env, next } = context;
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
      return next(); // authenticated -> serve the requested asset
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
