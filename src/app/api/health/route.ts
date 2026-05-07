import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { redis } from "@/lib/redis";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const checks = {
    ok: true as boolean,
    db: false,
    redis: false,
    uptime: process.uptime(),
    version: process.env.npm_package_version ?? "0.0.0",
  };

  try {
    await prisma.$queryRaw`SELECT 1`;
    checks.db = true;
  } catch {
    checks.ok = false;
  }

  try {
    await redis.ping();
    checks.redis = true;
  } catch {
    checks.ok = false;
  }

  return NextResponse.json(checks, { status: checks.ok ? 200 : 503 });
}
