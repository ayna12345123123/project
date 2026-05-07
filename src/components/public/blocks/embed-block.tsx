function detectKind(url: string): "youtube" | "tiktok" | "spotify" | "iframe" {
  if (/youtube\.com|youtu\.be/.test(url)) return "youtube";
  if (/tiktok\.com/.test(url)) return "tiktok";
  if (/spotify\.com/.test(url)) return "spotify";
  return "iframe";
}

function youtubeEmbedUrl(url: string): string {
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) {
      return `https://www.youtube.com/embed${u.pathname}`;
    }
    const id = u.searchParams.get("v");
    return id ? `https://www.youtube.com/embed/${id}` : url;
  } catch {
    return url;
  }
}

function spotifyEmbedUrl(url: string): string {
  try {
    const u = new URL(url);
    return `https://open.spotify.com/embed${u.pathname}`;
  } catch {
    return url;
  }
}

export function EmbedBlock({ data }: { data: Record<string, unknown> }) {
  const url = typeof data.url === "string" ? data.url : "";
  if (!url) return null;
  const explicit = typeof data.kind === "string" ? data.kind : null;
  const kind = (explicit as ReturnType<typeof detectKind>) ?? detectKind(url);
  const embedUrl =
    kind === "youtube" ? youtubeEmbedUrl(url) : kind === "spotify" ? spotifyEmbedUrl(url) : url;
  const aspect = kind === "spotify" ? "aspect-[16/8]" : "aspect-video";
  return (
    <div className={`overflow-hidden rounded-[var(--lf-radius)] ring-1 ring-current/10 ${aspect}`}>
      <iframe
        src={embedUrl}
        className="size-full"
        loading="lazy"
        allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}
