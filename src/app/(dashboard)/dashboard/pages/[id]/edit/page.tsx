import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { prisma } from "@/lib/prisma";
import { PageBuilder } from "@/features/builder/page-builder";

interface Params {
  params: Promise<{ id: string }>;
}

export const metadata = { title: "Edit page" };

export default async function EditPagePage({ params }: Params) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user) return null;

  const page = await prisma.page.findFirst({
    where: { id, userId: session.user.id, deletedAt: null },
    include: {
      blocks: { where: { deletedAt: null }, orderBy: { order: "asc" } },
      theme: true,
    },
  });
  if (!page) notFound();

  return (
    <PageBuilder
      page={{
        id: page.id,
        slug: page.slug,
        title: page.title,
        description: page.description,
        isPublished: page.isPublished,
        blocks: page.blocks.map((b) => ({
          id: b.id,
          type: b.type,
          order: b.order,
          hidden: b.hidden,
          label: b.label,
          url: b.url,
          content: (b.content as Record<string, unknown>) ?? {},
        })),
        theme: page.theme
          ? { tokens: (page.theme.tokens as Record<string, unknown>) ?? {} }
          : null,
      }}
    />
  );
}
