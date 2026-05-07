import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { redis } from "@/lib/redis";
import { resolveFromHeaders } from "@/lib/geo";
import { sha256Hex } from "@/lib/crypto";

export const runtime = "nodejs";

interface Ctx {
  params: Promise<{ code: string }>;
}

export async function GET(req: Request, { params }: Ctx) {
  const { code } = await params;
  const link = await prisma.shortLink.findUnique({
    where: { code },
    select: { id: true, url: true, pageId: true, userId: true },
  });
  if (!link) {
    return new Response("Not found", { status: 404 });
  }

  // Fire-and-forget: increment hit counter + push event
  void prisma.shortLink.update({ where: { id: link.id }, data: { hits: { increment: 1 } } }).catch(() => undefined);

  const headers = new Headers(req.headers);
  const geo = resolveFromHeaders(headers);
  const visitorId = geo.ip ? sha256Hex(`${geo.ip}:${new Date().toISOString().slice(0, 10)}`).slice(0, 16) : "";
  const args: string[] = [];
  for (const [k, v] of Object.entries({
    ts: Date.now(),
    type: "BLOCK_CLICK",
    pageId: link.pageId ?? "",
    blockId: "",
    visitorId,
    ipHash: geo.ip ? sha256Hex(geo.ip) : "",
    country: geo.country,
    device: geo.device,
    os: geo.os,
    browser: geo.browser,
    referer: "",
  })) {
    args.push(k, String(v));
  }
  void redis.xadd("analytics:stream", "MAXLEN", "~", "100000", "*", ...args).catch(() => undefined);

  redirect(link.url);
}
