import Link from "next/link";
import { redirect } from "next/navigation";
import { BarChart3, Home, Layout, Settings, Wand2, LogOut } from "lucide-react";
import { auth, signOut } from "@/auth";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: Home },
  { href: "/dashboard/pages", label: "Pages", icon: Layout },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/ai", label: "AI co-pilot", icon: Wand2 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) redirect("/login");

  const initials = (session.user.name ?? session.user.email ?? "U")
    .split(/\s+/)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .slice(0, 2)
    .join("");

  return (
    <div className="grid min-h-screen grid-cols-[260px_1fr]">
      <aside className="border-r bg-muted/20">
        <div className="flex h-16 items-center gap-2 px-6 border-b">
          <span className="grid size-8 place-items-center rounded-lg bg-accent text-accent-foreground font-bold">
            L
          </span>
          <span className="font-semibold">Linkforge</span>
        </div>
        <nav className="space-y-1 p-3">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/10 hover:text-foreground",
              )}
            >
              <n.icon className="size-4" />
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="absolute bottom-0 w-[260px] border-t p-3">
          <div className="flex items-center gap-3">
            <Avatar>
              <AvatarImage src={session.user.image ?? undefined} alt={session.user.name ?? ""} />
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{session.user.name ?? session.user.email}</div>
              <div className="truncate text-xs text-muted-foreground">@{session.user.username}</div>
            </div>
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/" });
              }}
            >
              <Button type="submit" size="icon" variant="ghost" aria-label="Sign out">
                <LogOut className="size-4" />
              </Button>
            </form>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="flex h-16 items-center justify-end border-b px-6">
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-auto p-6 md:p-10">{children}</main>
      </div>
    </div>
  );
}
