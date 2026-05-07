import { Github, Instagram, Linkedin, Mail, Twitter, Youtube } from "lucide-react";
import type { ComponentType } from "react";

const ICONS: Record<string, ComponentType<{ className?: string }>> = {
  twitter: Twitter,
  github: Github,
  instagram: Instagram,
  linkedin: Linkedin,
  youtube: Youtube,
  email: Mail,
};

export function SocialBlock({
  id,
  data,
  isEditing,
}: {
  id: string;
  data: Record<string, unknown>;
  isEditing: boolean;
}) {
  const items = Array.isArray(data.items)
    ? (data.items as { kind: string; href: string }[])
    : [];
  if (items.length === 0) return null;
  return (
    <div className="flex justify-center gap-3 py-2">
      {items.map((it, i) => {
        const Icon = ICONS[it.kind] ?? Mail;
        return (
          <a
            key={i}
            href={isEditing ? "#" : it.href}
            target={isEditing ? undefined : "_blank"}
            rel="noopener noreferrer"
            onClick={isEditing ? (e) => e.preventDefault() : undefined}
            data-track-block-id={id}
            className="grid size-10 place-items-center rounded-full bg-[color:var(--lf-surface)] ring-1 ring-current/10 transition hover:ring-current/30"
            aria-label={it.kind}
          >
            <Icon className="size-4" />
          </a>
        );
      })}
    </div>
  );
}
