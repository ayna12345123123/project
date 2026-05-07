import Link from "next/link";
import { type Block, type Page, type Theme, BlockType } from "@prisma/client";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { LinkBlock } from "./blocks/link-block";
import { TextBlock } from "./blocks/text-block";
import { ButtonBlock } from "./blocks/button-block";
import { ImageBlock } from "./blocks/image-block";
import { EmbedBlock } from "./blocks/embed-block";
import { SocialBlock } from "./blocks/social-block";
import { DividerBlock } from "./blocks/divider-block";
import { HeaderBlock } from "./blocks/header-block";
import { FaqBlock } from "./blocks/faq-block";
import { GalleryBlock } from "./blocks/gallery-block";
import { CountdownBlock } from "./blocks/countdown-block";

type PageWithRelations = Page & { blocks: Block[]; theme: Theme | null };

export function PageRenderer({ page, isEditing = false }: { page: PageWithRelations; isEditing?: boolean }) {
  const tokens = (page.theme?.tokens as Record<string, string> | undefined) ?? {};
  const cssVars: React.CSSProperties = {
    ["--lf-bg" as string]: tokens.background ?? "#FAFAFA",
    ["--lf-surface" as string]: tokens.surface ?? "#FFFFFF",
    ["--lf-text" as string]: tokens.text ?? "#0A0A0A",
    ["--lf-accent" as string]: tokens.accent ?? "#7C3AED",
    ["--lf-radius" as string]: `${tokens.radius ?? 16}px`,
  };
  const blocks = page.blocks.filter((b) => !b.hidden && !b.deletedAt).sort((a, b) => a.order - b.order);

  return (
    <div
      className="min-h-screen px-4 py-10"
      style={{ ...cssVars, background: "var(--lf-bg)", color: "var(--lf-text)" }}
    >
      <div className="mx-auto flex max-w-md flex-col gap-3">
        {blocks.map((b) => (
          <BlockSwitch key={b.id} block={b} isEditing={isEditing} />
        ))}
        {blocks.length === 0 && (
          <div className="rounded-2xl border border-dashed border-current/20 p-10 text-center text-sm opacity-70">
            This page has no blocks yet.
          </div>
        )}
        <p className="mt-6 text-center text-xs opacity-60">
          Made with{" "}
          <Link href="/" className="underline-offset-4 hover:underline">
            Linkforge
          </Link>
        </p>
      </div>
    </div>
  );
}

function BlockSwitch({ block, isEditing }: { block: Block; isEditing: boolean }) {
  const data = block.content as Record<string, unknown>;
  switch (block.type) {
    case BlockType.HEADER:
      return <HeaderBlock data={data} />;
    case BlockType.AVATAR:
      return <AvatarRenderer data={data} />;
    case BlockType.LINK:
      return <LinkBlock id={block.id} data={data} isEditing={isEditing} label={block.label} url={block.url} />;
    case BlockType.BUTTON:
      return <ButtonBlock id={block.id} data={data} isEditing={isEditing} />;
    case BlockType.TEXT:
      return <TextBlock data={data} />;
    case BlockType.IMAGE:
      return <ImageBlock data={data} />;
    case BlockType.VIDEO:
    case BlockType.EMBED:
      return <EmbedBlock data={data} />;
    case BlockType.SOCIAL:
      return <SocialBlock data={data} id={block.id} isEditing={isEditing} />;
    case BlockType.DIVIDER:
      return <DividerBlock data={data} />;
    case BlockType.FAQ:
      return <FaqBlock data={data} />;
    case BlockType.GALLERY:
      return <GalleryBlock data={data} />;
    case BlockType.COUNTDOWN:
      return <CountdownBlock data={data} />;
    default:
      return null;
  }
}

function AvatarRenderer({ data }: { data: Record<string, unknown> }) {
  const src = typeof data.src === "string" ? data.src : null;
  return (
    <div className="flex justify-center pt-4">
      <Avatar className="size-20 ring-2 ring-current/10">
        <AvatarImage src={src ?? undefined} alt="avatar" />
        <AvatarFallback>L</AvatarFallback>
      </Avatar>
    </div>
  );
}
