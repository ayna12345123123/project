/**
 * Pull geo + UA data from request headers.  In production we run behind
 * Cloudflare/Nginx which sets `cf-ipcountry` / `x-forwarded-for`.  In dev we
 * fall back to "ZZ" (unknown country).
 */
import { UAParser } from "ua-parser-js";

export interface ResolvedGeo {
  ip: string | null;
  country: string;
  userAgent: string | null;
  device: string;
  os: string;
  browser: string;
}

export function resolveFromHeaders(headers: Headers): ResolvedGeo {
  const ip =
    headers.get("cf-connecting-ip") ??
    (headers.get("x-forwarded-for") ?? "").split(",")[0]?.trim() ??
    headers.get("x-real-ip") ??
    null;
  const country =
    headers.get("cf-ipcountry") ?? headers.get("x-vercel-ip-country") ?? "ZZ";
  const ua = headers.get("user-agent");
  const parsed = new UAParser(ua ?? undefined).getResult();
  return {
    ip: ip ?? null,
    country: country.toUpperCase(),
    userAgent: ua,
    device: parsed.device.type ?? "desktop",
    os: parsed.os.name ?? "unknown",
    browser: parsed.browser.name ?? "unknown",
  };
}

const BOT_RE =
  /bot|spider|crawler|slurp|facebookexternalhit|embedly|ia_archiver|preview|fetch/i;

export function isLikelyBot(userAgent: string | null): boolean {
  if (!userAgent) return true;
  return BOT_RE.test(userAgent);
}
