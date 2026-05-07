/* eslint-disable @next/next/no-img-element */
export function ImageBlock({ data }: { data: Record<string, unknown> }) {
  const src = typeof data.src === "string" ? data.src : "";
  const alt = typeof data.alt === "string" ? data.alt : "";
  const href = typeof data.href === "string" ? data.href : null;
  if (!src) return null;
  const img = (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className="block w-full rounded-[var(--lf-radius)] object-cover"
    />
  );
  if (!href) return img;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="block">
      {img}
    </a>
  );
}
