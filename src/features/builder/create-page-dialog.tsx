"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toaster";

export function CreatePageDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      const res = await fetch("/api/pages", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, slug }),
      });
      const json = await res.json();
      if (!res.ok || json.ok === false) {
        toast({
          variant: "destructive",
          title: "Couldn't create page",
          description: json?.message ?? "Try a different slug.",
        });
        return;
      }
      setOpen(false);
      router.push(`/dashboard/pages/${json.data.id}/edit`);
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="accent">
          <Plus className="mr-1 size-4" />
          New page
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create page</DialogTitle>
          <DialogDescription>
            Pick a title and a public URL slug. You can change both later.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="page-title">Title</Label>
            <Input
              id="page-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My link page"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="page-slug">Slug</Label>
            <div className="flex">
              <span className="inline-flex items-center rounded-l-md border border-r-0 bg-muted px-3 text-sm text-muted-foreground">
                /u/
              </span>
              <Input
                id="page-slug"
                className="rounded-l-none"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="my-page"
                pattern="^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$"
                required
              />
            </div>
          </div>
          <Button type="submit" className="w-full" variant="accent" disabled={pending}>
            {pending && <Loader2 className="mr-2 size-4 animate-spin" />}
            Create page
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
