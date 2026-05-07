/**
 * Block schema registry.  Each block kind is described by a Zod schema so the
 * editor inspector and the API both validate the same way.  Add a new block
 * by creating a schema, a renderer (in `components/public/blocks`) and an
 * inspector (optional, in `components/builder/inspectors`) — nothing else.
 */
import { z } from "zod";

export const linkBlockSchema = z.object({
  label: z.string().min(1).max(120),
  url: z.string().url(),
  icon: z.string().optional(),
});

export const textBlockSchema = z.object({
  text: z.string().min(1).max(4000),
  align: z.enum(["left", "center", "right"]).default("left"),
});

export const buttonBlockSchema = z.object({
  label: z.string().min(1).max(80),
  url: z.string().url(),
  variant: z.enum(["primary", "outline", "ghost"]).default("primary"),
});

export const imageBlockSchema = z.object({
  src: z.string().url(),
  alt: z.string().max(160).optional(),
  href: z.string().url().optional(),
});

export const embedBlockSchema = z.object({
  url: z.string().url(),
  // Optional explicit kind; otherwise the renderer infers from the host
  kind: z.enum(["youtube", "tiktok", "spotify", "telegram", "soundcloud", "iframe"]).optional(),
});

export const dividerBlockSchema = z.object({
  spacing: z.number().int().min(0).max(96).default(16),
});

export const socialBlockSchema = z.object({
  items: z.array(
    z.object({
      kind: z.enum(["twitter", "github", "instagram", "tiktok", "youtube", "linkedin", "email"]),
      href: z.string().min(1),
    }),
  ),
});

export const headerBlockSchema = z.object({
  title: z.string().min(1).max(120),
  subtitle: z.string().max(240).optional(),
});

export const avatarBlockSchema = z.object({
  src: z.string().url().nullable().optional(),
});

export const faqBlockSchema = z.object({
  items: z.array(z.object({ q: z.string().min(1), a: z.string().min(1) })).min(1),
});

export const formBlockSchema = z.object({
  title: z.string().min(1).max(120),
  fields: z
    .array(
      z.object({
        name: z.string().regex(/^[a-z][a-z0-9_]{0,30}$/),
        label: z.string().min(1).max(80),
        type: z.enum(["text", "email", "textarea"]),
        required: z.boolean().default(false),
      }),
    )
    .min(1)
    .max(8),
  submitLabel: z.string().min(1).max(40).default("Send"),
});

export const countdownBlockSchema = z.object({
  targetAt: z.string().datetime(),
  finishedText: z.string().max(80).optional(),
});

export const galleryBlockSchema = z.object({
  images: z.array(z.string().url()).min(1).max(12),
  layout: z.enum(["grid", "masonry"]).default("grid"),
});

export const donationBlockSchema = z.object({
  title: z.string().min(1).max(120).default("Buy me a coffee"),
  amounts: z.array(z.number().int().positive()).min(1).max(6),
  currency: z.string().length(3).default("USD"),
});

export const productBlockSchema = z.object({
  title: z.string().min(1).max(120),
  priceMinor: z.number().int().positive(),
  currency: z.string().length(3).default("USD"),
  description: z.string().max(500).optional(),
  imageUrl: z.string().url().optional(),
});

export const mapBlockSchema = z.object({
  query: z.string().min(1).max(160),
  zoom: z.number().int().min(1).max(20).default(13),
});

export type BlockKind =
  | "LINK"
  | "TEXT"
  | "BUTTON"
  | "IMAGE"
  | "VIDEO"
  | "EMBED"
  | "DIVIDER"
  | "SOCIAL"
  | "HEADER"
  | "AVATAR"
  | "FAQ"
  | "FORM"
  | "COUNTDOWN"
  | "GALLERY"
  | "DONATION"
  | "PRODUCT"
  | "MAP";

export const blockSchemas = {
  LINK: linkBlockSchema,
  TEXT: textBlockSchema,
  BUTTON: buttonBlockSchema,
  IMAGE: imageBlockSchema,
  VIDEO: embedBlockSchema,
  EMBED: embedBlockSchema,
  DIVIDER: dividerBlockSchema,
  SOCIAL: socialBlockSchema,
  HEADER: headerBlockSchema,
  AVATAR: avatarBlockSchema,
  FAQ: faqBlockSchema,
  FORM: formBlockSchema,
  COUNTDOWN: countdownBlockSchema,
  GALLERY: galleryBlockSchema,
  DONATION: donationBlockSchema,
  PRODUCT: productBlockSchema,
  MAP: mapBlockSchema,
} as const satisfies Record<BlockKind, z.ZodTypeAny>;

export function validateBlockContent(kind: BlockKind, content: unknown) {
  const schema = blockSchemas[kind];
  return schema.safeParse(content);
}

export const BLOCK_PALETTE: { kind: BlockKind; label: string; description: string }[] = [
  { kind: "HEADER", label: "Header", description: "Title and subtitle" },
  { kind: "AVATAR", label: "Avatar", description: "Profile photo" },
  { kind: "LINK", label: "Link", description: "A trackable button-style link" },
  { kind: "BUTTON", label: "Button", description: "Primary CTA" },
  { kind: "TEXT", label: "Text", description: "Markdown text" },
  { kind: "IMAGE", label: "Image", description: "Optimised image" },
  { kind: "EMBED", label: "Embed", description: "YouTube / TikTok / Spotify" },
  { kind: "SOCIAL", label: "Socials", description: "Row of social icons" },
  { kind: "FORM", label: "Form", description: "Capture leads" },
  { kind: "FAQ", label: "FAQ", description: "Q&A list" },
  { kind: "COUNTDOWN", label: "Countdown", description: "Live countdown to a date" },
  { kind: "GALLERY", label: "Gallery", description: "Image grid" },
  { kind: "DIVIDER", label: "Divider", description: "Spacer / hairline" },
];
