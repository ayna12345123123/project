"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Eye, EyeOff, GripVertical, Loader2, Plus, Save, Trash2 } from "lucide-react";
import type { BlockType } from "@prisma/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toaster";
import { BLOCK_PALETTE, type BlockKind } from "@/features/builder/blocks";
import { LivePreview } from "@/features/builder/live-preview";

type EditorBlock = {
  id: string;
  type: BlockType;
  order: number;
  hidden: boolean;
  label: string | null;
  url: string | null;
  content: Record<string, unknown>;
};

type EditorPage = {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  isPublished: boolean;
  blocks: EditorBlock[];
  theme: { tokens: Record<string, unknown> } | null;
};

export function PageBuilder({ page }: { page: EditorPage }) {
  const router = useRouter();
  const [title, setTitle] = useState(page.title);
  const [description, setDescription] = useState(page.description ?? "");
  const [isPublished, setIsPublished] = useState(page.isPublished);
  const [blocks, setBlocks] = useState<EditorBlock[]>(page.blocks);
  const [pending, startTransition] = useTransition();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setBlocks((items) => {
      const oldIndex = items.findIndex((i) => i.id === active.id);
      const newIndex = items.findIndex((i) => i.id === over.id);
      const next = arrayMove(items, oldIndex, newIndex).map((b, i) => ({ ...b, order: i }));
      void persistOrder(next.map((b) => b.id));
      return next;
    });
  }

  async function persistOrder(orderedIds: string[]) {
    await fetch(`/api/pages/${page.id}/blocks/reorder`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ orderedIds }),
    });
  }

  async function addBlock(kind: BlockKind) {
    const res = await fetch(`/api/pages/${page.id}/blocks`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type: kind }),
    });
    const json = await res.json();
    if (!res.ok || json.ok === false) {
      toast({ variant: "destructive", title: "Couldn't add block", description: json?.message ?? "Try again." });
      return;
    }
    setBlocks((b) => [...b, json.data]);
  }

  async function updateBlock(id: string, patch: Partial<EditorBlock>) {
    setBlocks((all) => all.map((b) => (b.id === id ? { ...b, ...patch } : b)));
    await fetch(`/api/pages/${page.id}/blocks/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    });
  }

  async function deleteBlock(id: string) {
    setBlocks((all) => all.filter((b) => b.id !== id));
    await fetch(`/api/pages/${page.id}/blocks/${id}`, { method: "DELETE" });
  }

  function savePage() {
    startTransition(async () => {
      const res = await fetch(`/api/pages/${page.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, description, isPublished }),
      });
      const json = await res.json();
      if (!res.ok || json.ok === false) {
        toast({ variant: "destructive", title: "Save failed", description: json?.message ?? "" });
        return;
      }
      toast({ variant: "success", title: "Saved" });
      router.refresh();
    });
  }

  // Persist title/description automatically (debounced)
  useEffect(() => {
    const id = setTimeout(() => {
      void fetch(`/api/pages/${page.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, description }),
      });
    }, 600);
    return () => clearTimeout(id);
  }, [title, description, page.id]);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <Input
              className="border-0 px-0 text-2xl font-semibold focus-visible:ring-0"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">/u/{page.slug}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Switch checked={isPublished} onCheckedChange={setIsPublished} id="publish" />
              <Label htmlFor="publish" className="text-sm">Publish</Label>
            </div>
            <Button onClick={savePage} variant="accent" disabled={pending}>
              {pending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Save className="mr-2 size-4" />}
              Save
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Blocks</CardTitle>
          </CardHeader>
          <CardContent>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
              <SortableContext items={blocks.map((b) => b.id)} strategy={verticalListSortingStrategy}>
                <ul className="space-y-3">
                  {blocks.map((b) => (
                    <SortableBlockRow key={b.id} block={b} onChange={updateBlock} onDelete={deleteBlock} />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Add block</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {BLOCK_PALETTE.map((p) => (
                <Button key={p.kind} variant="outline" onClick={() => addBlock(p.kind)} className="justify-start">
                  <Plus className="mr-2 size-4" />
                  {p.label}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>SEO</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="desc">Description</Label>
              <Textarea
                id="desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What this page is about — used in OpenGraph & Twitter cards."
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="lg:sticky lg:top-6">
        <Tabs defaultValue="mobile" className="space-y-3">
          <TabsList>
            <TabsTrigger value="mobile">Mobile</TabsTrigger>
            <TabsTrigger value="desktop">Desktop</TabsTrigger>
          </TabsList>
          <TabsContent value="mobile">
            <LivePreview
              page={{
                id: page.id,
                slug: page.slug,
                title,
                description,
                isPublished,
                ogImageUrl: null,
                faviconUrl: null,
                metaJson: null,
                blocks: blocks.map((b) => ({
                  ...b,
                  content: b.content,
                })),
                theme: page.theme,
              }}
              width={380}
            />
          </TabsContent>
          <TabsContent value="desktop">
            <LivePreview
              page={{
                id: page.id,
                slug: page.slug,
                title,
                description,
                isPublished,
                ogImageUrl: null,
                faviconUrl: null,
                metaJson: null,
                blocks: blocks.map((b) => ({
                  ...b,
                  content: b.content,
                })),
                theme: page.theme,
              }}
              width={760}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function SortableBlockRow({
  block,
  onChange,
  onDelete,
}: {
  block: EditorBlock;
  onChange: (id: string, patch: Partial<EditorBlock>) => void;
  onDelete: (id: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: block.id,
  });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  const labelValue =
    block.label ?? (typeof block.content?.label === "string" ? (block.content.label as string) : "");
  const urlValue = block.url ?? (typeof block.content?.url === "string" ? (block.content.url as string) : "");

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 rounded-md border bg-card p-3 shadow-sm"
    >
      <button
        type="button"
        aria-label="Drag block"
        className="cursor-grab text-muted-foreground"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="size-4" />
      </button>
      <div className="grid flex-1 gap-2 md:grid-cols-2">
        <Input
          value={labelValue}
          onChange={(e) => {
            const v = e.target.value;
            onChange(block.id, { label: v, content: { ...block.content, label: v } });
          }}
          placeholder={`${block.type.toLowerCase()} label`}
        />
        <Input
          value={urlValue}
          onChange={(e) => {
            const v = e.target.value;
            onChange(block.id, { url: v, content: { ...block.content, url: v } });
          }}
          placeholder="https://example.com"
        />
      </div>
      <Button
        size="icon"
        variant="ghost"
        aria-label="Toggle visibility"
        onClick={() => onChange(block.id, { hidden: !block.hidden })}
      >
        {block.hidden ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </Button>
      <Button size="icon" variant="ghost" aria-label="Delete block" onClick={() => onDelete(block.id)}>
        <Trash2 className="size-4" />
      </Button>
    </li>
  );
}
