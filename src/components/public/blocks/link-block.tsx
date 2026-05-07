import { ArrowUpRight } from "lucide-react";

export function LinkBlock({
  id,
  data,
  label,
  url,
  isEditing,
}: {
  id: string;
  data: Record<string, unknown>;
  label: string | null;
  url: string | null;
  isEditing: boolean;
}) {
  const finalLabel = label ?? (typeof data.label === "string" ? data.label : "Link");
  const finalUrl = url ?? (typeof data.url === "string" ? data.url : "#");
  const props: Record<string, unknown> = isEditing
    ? { onClick: (e: React.MouseEvent) => e.preventDefault(), href: "#", role: "link" }
    : {
        href: finalUrl,
        target: "_blank",
        rel: "noopener noreferrer",
        "data-track-block-id": id,
      };
  return (
    <a
      {...(props as React.AnchorHTMLAttributes<HTMLAnchorElement>)}
      className="group flex items-center justify-between rounded-[var(--lf-radius)] bg-[color:var(--lf-surface)] px-5 py-4 text-sm font-medium shadow-sm ring-1 ring-current/10 transition-transform hover:scale-[1.01] hover:ring-current/30 active:scale-[0.99]"
    >
      <span className="truncate">{finalLabel}</span>
      <ArrowUpRight className="size-4 opacity-50 transition group-hover:opacity-100" />
    </a>
  );
}
