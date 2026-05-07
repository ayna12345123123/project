import argon2 from "argon2";
import { z } from "zod";

import { errors, ok } from "@/lib/api";
import { prisma } from "@/lib/prisma";
import { rateLimit } from "@/lib/rate-limit";
import { resolveFromHeaders } from "@/lib/geo";
import { isValidSlug, slugify } from "@/lib/utils";
import { logger } from "@/lib/logger";

export const runtime = "nodejs";

const bodySchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(8).max(256),
  username: z
    .string()
    .min(3)
    .max(32)
    .refine(isValidSlug, "Username must be 3-32 chars, letters/digits/hyphens only"),
  name: z.string().min(1).max(64).optional(),
  marketingOptIn: z.boolean().optional().default(false),
  referralCode: z.string().max(64).optional(),
});

export async function POST(req: Request) {
  const ipInfo = resolveFromHeaders(new Headers(req.headers));
  const ipKey = ipInfo.ip ?? "unknown";

  const rl = await rateLimit(`auth:register:${ipKey}`, 5, 5);
  if (!rl.ok) return errors.tooMany();

  const json = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(json);
  if (!parsed.success) {
    return errors.badRequest("Invalid input", parsed.error.flatten().fieldErrors);
  }

  const { email, password, username, name, marketingOptIn, referralCode } = parsed.data;
  const slug = slugify(username);

  const reserved = await prisma.reservedSlug.findUnique({ where: { slug } });
  if (reserved) return errors.conflict("This username is reserved");

  const existing = await prisma.user.findFirst({
    where: { OR: [{ email: email.toLowerCase() }, { username: slug }] },
    select: { id: true, email: true, username: true },
  });
  if (existing) {
    return errors.conflict(
      existing.email === email.toLowerCase() ? "Email already registered" : "Username taken",
    );
  }

  const passwordHash = await argon2.hash(password, { type: argon2.argon2id });

  const user = await prisma.user.create({
    data: {
      email: email.toLowerCase(),
      passwordHash,
      username: slug,
      name: name ?? slug,
      marketingOptIn: !!marketingOptIn,
      referredByCode: referralCode || undefined,
    },
    select: { id: true, email: true, username: true },
  });

  logger.info({ userId: user.id }, "auth.register.success");

  return ok({ id: user.id, email: user.email, username: user.username }, { status: 201 });
}
