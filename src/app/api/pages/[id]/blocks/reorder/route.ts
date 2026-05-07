import { z } from "zod";

import { auth } from "@/auth";
import { errors, ok } from "@/lib/api";
import { prisma } from "@/lib/prisma";
import { rateLimit } from "@/lib/rate-limit";
import { env } from "@/lib/env";

export const runtime = "nodejs";

const schema = z.object({
  orderedIds: z.array(z.string().min(1)).min(1).max(200),
});

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function POST(req: Request, { params }: Ctx) {
  const session = await auth();
  if (!session?.user) return errors.unauthorized();
  const { id } = await params;

  const rl = await rateLimit(`blocks:reorder:${session.user.id}`, 60, env.RATE_LIMIT_WRITES_PER_MIN);
  if (!rl.ok) return errors.tooMany();

  const own = await prisma.page.findFirst({
    where: { id, userId: session.user.id, deletedAt: null },
    select: { id: true },
  });
  if (!own) return errors.notFound();

  const body = await req.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) return errors.badRequest("Invalid input");

  const updates = parsed.data.orderedIds.map((blockId, order) =>
    prisma.block.updateMany({
      where: { id: blockId, pageId: id, deletedAt: null },
      data: { order },
    }),
  );

  await prisma.$transaction([
    ...updates,
    prisma.page.update({ where: { id }, data: { version: { increment: 1 } } }),
  ]);

  return ok({ ok: true });
}
