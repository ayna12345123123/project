import { auth } from "@/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { prisma } from "@/lib/prisma";
import { AnalyticsChart } from "@/features/analytics/analytics-chart";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage() {
  const session = await auth();
  if (!session?.user) return null;

  const since = new Date();
  since.setDate(since.getDate() - 29);
  since.setHours(0, 0, 0, 0);

  const rows = await prisma.analyticsDaily.findMany({
    where: { ownerId: session.user.id, day: { gte: since } },
    orderBy: { day: "asc" },
    select: { day: true, views: true, uniques: true, clicks: true },
  });

  // Fill missing days with zeros so charts render correctly even with sparse data
  const days = new Map<string, { views: number; uniques: number; clicks: number }>();
  for (let i = 0; i < 30; i++) {
    const d = new Date(since);
    d.setDate(since.getDate() + i);
    days.set(d.toISOString().slice(0, 10), { views: 0, uniques: 0, clicks: 0 });
  }
  for (const r of rows) {
    const k = r.day.toISOString().slice(0, 10);
    days.set(k, { views: r.views, uniques: r.uniques, clicks: r.clicks });
  }
  const series = Array.from(days, ([day, v]) => ({ day, ...v }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Analytics</h1>
        <p className="mt-1 text-muted-foreground">Last 30 days · roll-ups updated continuously.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Views vs clicks</CardTitle>
          <CardDescription>Aggregated across all pages.</CardDescription>
        </CardHeader>
        <CardContent className="h-[320px]">
          <AnalyticsChart data={series} />
        </CardContent>
      </Card>
    </div>
  );
}
