import { z } from "zod";

import { auth } from "@/auth";
import { errors, ok } from "@/lib/api";
import { prisma } from "@/lib/prisma";
import { rateLimit } from "@/lib/rate-limit";
import { isValidSlug, slugify } from "@/lib/utils";
import { env } from "@/lib/env";

export const runtime = "nodejs";

const bodySchema = z.object({
  title: z.string().min(1).max(160),
  slug: z.string().min(3).max(32).refine(isValidSlug, "Invalid slug"),
});

export async function GET() {
  const session = await auth();
  if (!session?.user) return errors.unauthorized();

  const pages = await prisma.page.findMany({
    where: { userId: session.user.id, deletedAt: null },
    orderBy: { updatedAt: "desc" },
    select: {
      id: true,
      slug: true,
      title: true,
      isPublished: true,
      updatedAt: true,
      createdAt: true,
    },
  });
  return ok(pages);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return errors.unauthorized();

  const rl = await rateLimit(`pages:create:${session.user.id}`, 10, env.RATE_LIMIT_WRITES_PER_MIN);
  if (!rl.ok) return errors.tooMany();

  const body = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) return errors.badRequest("Invalid input", parsed.error.flatten().fieldErrors);

  const slug = slugify(parsed.data.slug);
  if (!isValidSlug(slug)) return errors.badRequest("Invalid slug after normalisation");

  const reserved = await prisma.reservedSlug.findUnique({ where: { slug } });
  if (reserved) return errors.conflict("This slug is reserved");

  const existing = await prisma.page.findUnique({ where: { slug }, select: { id: true } });
  if (existing) return errors.conflict("Slug already taken");

  const page = await prisma.page.create({
    data: {
      userId: session.user.id,
      title: parsed.data.title,
      slug,
      theme: {
        create: {
          presetKey: "minimal-light",
          tokens: {
            background: "#FAFAFA",
            surface: "#FFFFFF",
            text: "#0A0A0A",
            accent: "#7C3AED",
            radius: 16,
            font: "Inter",
          },
        },
      },
      blocks: {
        createMany: {
          data: [
            {
              type: "AVATAR",
              order: 0,
              content: { src: null },
            },
            {
              type: "HEADER",
              order: 1,
              content: { title: parsed.data.title, subtitle: `@${session.user.username}` },
            },
          ],
        },
      },
    },
    select: { id: true, slug: true, title: true },
  });

  return ok(page, { status: 201 });
}
