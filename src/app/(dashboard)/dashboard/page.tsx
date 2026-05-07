import Link from "next/link";
import { ArrowRight, Eye, MousePointerClick, Users } from "lucide-react";
import { auth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { prisma } from "@/lib/prisma";
import { formatNumber } from "@/lib/utils";

export const metadata = { title: "Dashboard" };

export default async function DashboardHomePage() {
  const session = await auth();
  if (!session?.user) return null;

  const userId = session.user.id;
  const since = new Date();
  since.setDate(since.getDate() - 30);

  const [pages, agg] = await Promise.all([
    prisma.page.findMany({
      where: { userId, deletedAt: null },
      orderBy: { updatedAt: "desc" },
      take: 5,
      select: { id: true, slug: true, title: true, isPublished: true, updatedAt: true },
    }),
    prisma.analyticsDaily.aggregate({
      where: { ownerId: userId, day: { gte: since } },
      _sum: { views: true, uniques: true, clicks: true },
    }),
  ]);

  const stats = [
    { label: "Views (30d)", value: agg._sum.views ?? 0, icon: Eye },
    { label: "Uniques (30d)", value: agg._sum.uniques ?? 0, icon: Users },
    { label: "Clicks (30d)", value: agg._sum.clicks ?? 0, icon: MousePointerClick },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Welcome back, {session.user.name ?? session.user.username}</h1>
          <p className="mt-1 text-muted-foreground">
            Here&apos;s a snapshot of how your pages performed in the last 30 days.
          </p>
        </div>
        <Button asChild variant="accent">
          <Link href="/dashboard/pages">
            New page <ArrowRight className="ml-1 size-4" />
          </Link>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{s.label}</CardTitle>
              <s.icon className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold tracking-tight">{formatNumber(s.value)}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent pages</CardTitle>
          <CardDescription>Your most recently updated pages.</CardDescription>
        </CardHeader>
        <CardContent>
          {pages.length === 0 ? (
            <div className="rounded-md border border-dashed p-10 text-center">
              <p className="text-sm text-muted-foreground">You don&apos;t have any pages yet.</p>
              <Button asChild className="mt-4" variant="accent">
                <Link href="/dashboard/pages">Create your first page</Link>
              </Button>
            </div>
          ) : (
            <ul className="divide-y">
              {pages.map((p) => (
                <li key={p.id} className="flex items-center justify-between py-3">
                  <div className="min-w-0">
                    <Link href={`/dashboard/pages/${p.id}/edit`} className="block truncate font-medium hover:underline">
                      {p.title}
                    </Link>
                    <div className="text-xs text-muted-foreground">
                      /u/{p.slug} · {p.isPublished ? "Published" : "Draft"} · updated{" "}
                      {p.updatedAt.toLocaleDateString()}
                    </div>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/u/${p.slug}`} target="_blank">
                      View
                    </Link>
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
