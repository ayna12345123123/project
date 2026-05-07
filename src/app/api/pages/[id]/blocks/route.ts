import { z } from "zod";
import { BlockType, type Prisma } from "@prisma/client";

import { auth } from "@/auth";
import { errors, ok } from "@/lib/api";
import { prisma } from "@/lib/prisma";
import { rateLimit } from "@/lib/rate-limit";
import { env } from "@/lib/env";

export const runtime = "nodejs";

const createSchema = z.object({
  type: z.nativeEnum(BlockType),
  content: z.record(z.unknown()).optional(),
});

interface Ctx {
  params: Promise<{ id: string }>;
}

const DEFAULT_CONTENT: Record<BlockType, Record<string, unknown>> = {
  LINK: { label: "New link", url: "https://example.com" },
  TEXT: { text: "Write something here…", align: "center" },
  BUTTON: { label: "Click me", url: "https://example.com", variant: "primary" },
  IMAGE: { src: "" },
  VIDEO: { url: "" },
  EMBED: { url: "" },
  DIVIDER: { spacing: 16 },
  SOCIAL: { items: [] },
  HEADER: { title: "Section", subtitle: "" },
  AVATAR: { src: null },
  FAQ: { items: [{ q: "Question", a: "Answer" }] },
  FORM: { title: "Contact", fields: [{ name: "email", label: "Email", type: "email", required: true }], submitLabel: "Send" },
  COUNTDOWN: { targetAt: new Date(Date.now() + 7 * 86_400_000).toISOString() },
  GALLERY: { images: [], layout: "grid" },
  DONATION: { title: "Buy me a coffee", amounts: [3, 5, 10], currency: "USD" },
  PRODUCT: { title: "Digital download", priceMinor: 1000, currency: "USD" },
  MAP: { query: "New York, NY", zoom: 13 },
};

export async function POST(req: Request, { params }: Ctx) {
  const session = await auth();
  if (!session?.user) return errors.unauthorized();
  const { id } = await params;

  const rl = await rateLimit(`blocks:create:${session.user.id}`, 60, env.RATE_LIMIT_WRITES_PER_MIN);
  if (!rl.ok) return errors.tooMany();

  const own = await prisma.page.findFirst({
    where: { id, userId: session.user.id, deletedAt: null },
    select: { id: true },
  });
  if (!own) return errors.notFound();

  const body = await req.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return errors.badRequest("Invalid input", parsed.error.flatten().fieldErrors);

  const last = await prisma.block.findFirst({
    where: { pageId: id, deletedAt: null },
    orderBy: { order: "desc" },
    select: { order: true },
  });
  const order = (last?.order ?? -1) + 1;
  const content = { ...DEFAULT_CONTENT[parsed.data.type], ...(parsed.data.content ?? {}) };

  const block = await prisma.block.create({
    data: {
      pageId: id,
      type: parsed.data.type,
      order,
      content: content as Prisma.InputJsonValue,
      label: typeof content.label === "string" ? content.label : null,
      url: typeof content.url === "string" ? content.url : null,
    },
    select: {
      id: true,
      type: true,
      order: true,
      hidden: true,
      label: true,
      url: true,
      content: true,
    },
  });

  // Bump page version so caches invalidate
  await prisma.page.update({ where: { id }, data: { version: { increment: 1 } } });

  return ok(block, { status: 201 });
}
