import { auth } from "@/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { prisma } from "@/lib/prisma";

export const metadata = { title: "Settings" };

export default async function SettingsPage() {
  const session = await auth();
  if (!session?.user) return null;

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      email: true,
      username: true,
      name: true,
      role: true,
      twoFactorEnabled: true,
      createdAt: true,
    },
  });

  if (!user) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-muted-foreground">Account, security, billing.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Public profile and contact info.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="Name" value={user.name ?? "—"} />
          <Row label="Username" value={`@${user.username}`} />
          <Row label="Email" value={user.email} />
          <Row label="Plan" value={<Badge variant={user.role === "PRO" ? "accent" : "outline"}>{user.role}</Badge>} />
          <Row label="Member since" value={user.createdAt.toLocaleDateString()} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Security</CardTitle>
          <CardDescription>Two-factor authentication, sessions and audit logs.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="2FA" value={<Badge variant={user.twoFactorEnabled ? "success" : "outline"}>{user.twoFactorEnabled ? "Enabled" : "Disabled"}</Badge>} />
          <p className="pt-2 text-xs text-muted-foreground">
            Device sessions and per-event audit logs are visible to ADMIN users in <code>/admin</code>.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-2 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
