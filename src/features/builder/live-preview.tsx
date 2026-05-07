"use client";

import type { BlockType } from "@prisma/client";
import { LinkBlock } from "@/components/public/blocks/link-block";
import { TextBlock } from "@/components/public/blocks/text-block";
import { ButtonBlock } from "@/components/public/blocks/button-block";
import { ImageBlock } from "@/components/public/blocks/image-block";
import { EmbedBlock } from "@/components/public/blocks/embed-block";
import { SocialBlock } from "@/components/public/blocks/social-block";
import { DividerBlock } from "@/components/public/blocks/divider-block";
import { HeaderBlock } from "@/components/public/blocks/header-block";
import { FaqBlock } from "@/components/public/blocks/faq-block";
import { GalleryBlock } from "@/components/public/blocks/gallery-block";
import { CountdownBlock } from "@/components/public/blocks/countdown-block";

interface LivePage {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  isPublished: boolean;
  ogImageUrl: string | null;
  faviconUrl: string | null;
  metaJson: unknown;
  blocks: {
    id: string;
    type: BlockType;
    order: number;
    hidden: boolean;
    label: string | null;
    url: string | null;
    content: Record<string, unknown>;
  }[];
  theme: { tokens: Record<string, unknown> } | null;
}

export function LivePreview({ page, width }: { page: LivePage; width: number }) {
  const tokens = (page.theme?.tokens as Record<string, string> | undefined) ?? {};
  const cssVars: React.CSSProperties = {
    ["--lf-bg" as string]: tokens.background ?? "#FAFAFA",
    ["--lf-surface" as string]: tokens.surface ?? "#FFFFFF",
    ["--lf-text" as string]: tokens.text ?? "#0A0A0A",
    ["--lf-accent" as string]: tokens.accent ?? "#7C3AED",
    ["--lf-radius" as string]: `${tokens.radius ?? 16}px`,
    background: "var(--lf-bg)",
    color: "var(--lf-text)",
  };
  const visible = page.blocks.filter((b) => !b.hidden).sort((a, b) => a.order - b.order);

  return (
    <div className="overflow-hidden rounded-2xl border shadow-sm">
      <div
        className="flex min-h-[640px] flex-col gap-3 px-6 py-10"
        style={{ ...cssVars, width: "100%", maxWidth: width }}
      >
        <div className="mx-auto flex w-full max-w-md flex-col gap-3">
          {visible.map((b) => {
            switch (b.type) {
              case "HEADER":
                return <HeaderBlock key={b.id} data={b.content} />;
              case "LINK":
                return <LinkBlock key={b.id} id={b.id} data={b.content} label={b.label} url={b.url} isEditing />;
              case "BUTTON":
                return <ButtonBlock key={b.id} id={b.id} data={b.content} isEditing />;
              case "TEXT":
                return <TextBlock key={b.id} data={b.content} />;
              case "IMAGE":
                return <ImageBlock key={b.id} data={b.content} />;
              case "VIDEO":
              case "EMBED":
                return <EmbedBlock key={b.id} data={b.content} />;
              case "SOCIAL":
                return <SocialBlock key={b.id} id={b.id} data={b.content} isEditing />;
              case "DIVIDER":
                return <DividerBlock key={b.id} data={b.content} />;
              case "FAQ":
                return <FaqBlock key={b.id} data={b.content} />;
              case "GALLERY":
                return <GalleryBlock key={b.id} data={b.content} />;
              case "COUNTDOWN":
                return <CountdownBlock key={b.id} data={b.content} />;
              default:
                return null;
            }
          })}
          {visible.length === 0 && (
            <div className="rounded-2xl border border-dashed border-current/20 p-10 text-center text-sm opacity-70">
              Add some blocks to see them appear here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
