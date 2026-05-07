import { Sparkles } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = { title: "AI co-pilot" };

export default function AiPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
          <Sparkles className="size-6 text-accent" />
          AI co-pilot
        </h1>
        <p className="mt-1 text-muted-foreground">
          Bio, theme, CTA and SEO suggestions — wired to your block library.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[
          { title: "Bio generator", description: "Three on-brand variants tailored to your audience." },
          { title: "Theme generator", description: "Color, font and gradient tokens from a single mood prompt." },
          { title: "CTA optimiser", description: "Bandit-driven CTA copy that learns from real clicks." },
          { title: "SEO audit", description: "JSON-LD + metadata diff with one-click apply." },
        ].map((f) => (
          <Card key={f.title}>
            <CardHeader>
              <CardTitle>{f.title}</CardTitle>
              <CardDescription>{f.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
                Wired up in <code>features/ai/*</code> and the <code>ai-generate</code> queue. UI coming in v1.2.
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
