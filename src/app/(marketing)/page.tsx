import Link from "next/link";
import { ArrowRight, BarChart3, Brush, Globe2, Lock, Sparkles, Wallet, Workflow, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const FEATURES = [
  {
    icon: Brush,
    title: "Drag-and-drop builder",
    description: "Beautiful blocks for links, embeds, products, forms, FAQ, countdowns and more — composed with a buttery editor.",
  },
  {
    icon: BarChart3,
    title: "Realtime analytics",
    description: "Views, clicks, GEO, devices, UTM funnels, top blocks. Daily roll-ups for fast charts, raw events for deep dives.",
  },
  {
    icon: Sparkles,
    title: "AI co-pilot",
    description: "Bio, theme, CTA and SEO suggestions in one click. A bandit optimiser quietly improves CTR while you sleep.",
  },
  {
    icon: Wallet,
    title: "Built-in monetisation",
    description: "Stripe-powered subscriptions, donations and digital products. Affiliate + referral tracking out of the box.",
  },
  {
    icon: Globe2,
    title: "Custom domains",
    description: "Bring your own domain and get HTTPS issued automatically. Multi-tenant architecture from day one.",
  },
  {
    icon: Lock,
    title: "Enterprise security",
    description: "Argon2id passwords, 2FA, device sessions, audit logs, RBAC, rate-limits, CSP, Let's Encrypt TLS.",
  },
  {
    icon: Workflow,
    title: "API + webhooks",
    description: "REST API with OpenAPI, scoped API keys, signed outbound webhooks. Pipe leads straight into your stack.",
  },
  {
    icon: Zap,
    title: "Edge-fast renderer",
    description: "Public pages SSR in <50 ms with Redis cache. Lighthouse 95+ across Performance / SEO / Accessibility / BP.",
  },
];

const TESTIMONIALS = [
  {
    quote:
      "Switched from Linktree on a Tuesday and saw a 2.4× lift in click-through by Friday. The AI optimiser does the boring work for me.",
    name: "Maya R.",
    role: "Indie maker · 38k followers",
  },
  {
    quote:
      "We host all our coaches on Linkforge. Custom domains, PRO themes and Stripe in one stack saved us from gluing 3 tools together.",
    name: "Daniel K.",
    role: "Founder · CoachStack",
  },
  {
    quote:
      "I needed analytics that match Plausible-quality, with proper UTM funnels. This is the first link-in-bio tool that delivers.",
    name: "Anaïs P.",
    role: "Growth lead · Bento Studio",
  },
];

const PRICING = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    cta: "Start free",
    features: [
      "1 page",
      "All core blocks",
      "Standard analytics (90 days)",
      "Linkforge subdomain",
    ],
  },
  {
    name: "PRO",
    price: "$8",
    cadence: "/month",
    cta: "Go PRO",
    highlight: true,
    features: [
      "Unlimited pages",
      "Custom domain + SSL",
      "AI co-pilot + A/B tests",
      "Donations & digital products",
      "Lifetime analytics retention",
    ],
  },
  {
    name: "Team",
    price: "$24",
    cadence: "/month",
    cta: "Talk to sales",
    features: [
      "5 seats included",
      "RBAC + audit logs",
      "Webhooks + API keys",
      "Priority support",
    ],
  },
];

const FAQS = [
  {
    q: "Is Linkforge open-source?",
    a: "Yes — the entire codebase is MIT-licensed. You can self-host on any VPS in minutes (see DEPLOYMENT.md).",
  },
  {
    q: "Can I bring my own domain?",
    a: "Yes. Add a TXT record, point an A record, and Linkforge auto-issues an SSL cert via Let's Encrypt. Available on PRO.",
  },
  {
    q: "How fast are the public pages?",
    a: "Sub-50 ms TTFB on Redis-cache hits, sub-200 ms cold. Pages ship under 30 KB of client JS.",
  },
  {
    q: "Do you take a cut of donations / product sales?",
    a: "0%. You connect your own Stripe account; we never touch your money.",
  },
];

export default function LandingPage() {
  return (
    <>
      <section className="relative overflow-hidden border-b">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-60" />
        <div className="container relative py-24 md:py-32">
          <div className="mx-auto max-w-3xl text-center">
            <Badge variant="accent" className="mb-6">
              <Sparkles className="mr-1 size-3" />
              Built for creators in 2026
            </Badge>
            <h1 className="text-balance text-5xl font-semibold tracking-tight md:text-7xl">
              One link.
              <span className="bg-gradient-to-r from-accent to-fuchsia-500 bg-clip-text text-transparent">
                {" "}
                Your whole world.
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-balance text-lg text-muted-foreground md:text-xl">
              The production-grade Linktree / Taplink alternative. Beautiful pages,
              first-class analytics, AI optimisation and Stripe payments — on a
              stack you can actually self-host.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg" variant="accent" className="px-6">
                <Link href="/register">
                  Create your page <ArrowRight className="ml-1 size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="#features">See what&apos;s inside</Link>
              </Button>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              No credit card · Free forever plan · Self-host in 5 minutes
            </p>
          </div>
        </div>
      </section>

      <section id="features" className="container py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Everything a serious creator needs
          </h2>
          <p className="mt-3 text-muted-foreground">
            Linktree-grade simplicity, Stripe-grade engineering. Built on Next.js
            15, Prisma, Redis and BullMQ — open and self-hostable.
          </p>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <Card key={f.title} className="border-border/60">
              <CardHeader>
                <div className="grid size-10 place-items-center rounded-lg bg-accent/10 text-accent">
                  <f.icon className="size-5" />
                </div>
                <CardTitle className="mt-4">{f.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>{f.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-y bg-muted/30 py-24">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Loved by creators who outgrew Linktree
            </h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {TESTIMONIALS.map((t) => (
              <Card key={t.name}>
                <CardContent className="space-y-4 p-6">
                  <p className="text-sm leading-relaxed">“{t.quote}”</p>
                  <div>
                    <div className="text-sm font-medium">{t.name}</div>
                    <div className="text-xs text-muted-foreground">{t.role}</div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="container py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Simple pricing</h2>
          <p className="mt-3 text-muted-foreground">
            Start free. Upgrade when you need analytics retention, AI, custom
            domains or product sales.
          </p>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {PRICING.map((p) => (
            <Card
              key={p.name}
              className={p.highlight ? "border-accent shadow-lg shadow-accent/10" : ""}
            >
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {p.name}
                  {p.highlight && <Badge variant="accent">Most popular</Badge>}
                </CardTitle>
                <div className="flex items-baseline gap-1 pt-2">
                  <span className="text-4xl font-semibold tracking-tight">{p.price}</span>
                  <span className="text-sm text-muted-foreground">{p.cadence}</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <ul className="space-y-2 text-sm">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <span className="mt-1.5 inline-block size-1.5 rounded-full bg-accent" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Button asChild className="w-full" variant={p.highlight ? "accent" : "outline"}>
                  <Link href="/register">{p.cta}</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section id="faq" className="border-t py-24">
        <div className="container max-w-3xl">
          <h2 className="text-center text-3xl font-semibold tracking-tight md:text-4xl">
            Frequently asked questions
          </h2>
          <div className="mt-12 space-y-3">
            {FAQS.map((f) => (
              <Card key={f.q}>
                <CardHeader>
                  <CardTitle className="text-base">{f.q}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-sm leading-relaxed">{f.a}</CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t bg-gradient-to-br from-accent/15 via-fuchsia-500/10 to-cyan-500/10 py-24">
        <div className="container max-w-3xl text-center">
          <h2 className="text-balance text-4xl font-semibold tracking-tight">
            Build a page that converts in under a minute.
          </h2>
          <p className="mt-3 text-muted-foreground">
            Linkforge is open, fast, and ready to scale with you.
          </p>
          <Button asChild size="lg" variant="accent" className="mt-8 px-6">
            <Link href="/register">
              Get started — it&apos;s free <ArrowRight className="ml-1 size-4" />
            </Link>
          </Button>
        </div>
      </section>
    </>
  );
}
