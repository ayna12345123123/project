/* eslint-disable @next/next/no-img-element */
export function GalleryBlock({ data }: { data: Record<string, unknown> }) {
  const images = Array.isArray(data.images) ? (data.images as string[]) : [];
  if (images.length === 0) return null;
  return (
    <div className="grid grid-cols-3 gap-2">
      {images.map((src, i) => (
        <img
          key={i}
          src={src}
          alt=""
          loading="lazy"
          className="aspect-square w-full rounded-[var(--lf-radius)] object-cover"
        />
      ))}
    </div>
  );
}
