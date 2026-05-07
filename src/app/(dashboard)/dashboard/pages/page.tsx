import Link from "next/link";
import { auth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { prisma } from "@/lib/prisma";
import { CreatePageDialog } from "@/features/builder/create-page-dialog";

export const metadata = { title: "Pages" };

export default async function PagesIndexPage() {
  const session = await auth();
  if (!session?.user) return null;

  const pages = await prisma.page.findMany({
    where: { userId: session.user.id, deletedAt: null },
    orderBy: { updatedAt: "desc" },
    select: { id: true, slug: true, title: true, isPublished: true, updatedAt: true },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Pages</h1>
          <p className="mt-1 text-muted-foreground">Your mini-landings and link-in-bio pages.</p>
        </div>
        <CreatePageDialog />
      </div>
      {pages.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 p-12 text-center">
            <CardTitle>Create your first page</CardTitle>
            <CardDescription>Pick a slug, drop in some blocks, and you&apos;re live in a minute.</CardDescription>
            <CreatePageDialog />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {pages.map((p) => (
            <Card key={p.id} className="transition-colors hover:border-accent">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2">
                  <span className="truncate">{p.title}</span>
                  <Badge variant={p.isPublished ? "success" : "outline"}>
                    {p.isPublished ? "Live" : "Draft"}
                  </Badge>
                </CardTitle>
                <CardDescription>/u/{p.slug}</CardDescription>
              </CardHeader>
              <CardContent className="flex justify-between text-xs text-muted-foreground">
                <span>Updated {p.updatedAt.toLocaleDateString()}</span>
                <div className="flex gap-2">
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/u/${p.slug}`} target="_blank">
                      View
                    </Link>
                  </Button>
                  <Button asChild size="sm" variant="accent">
                    <Link href={`/dashboard/pages/${p.id}/edit`}>Edit</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
