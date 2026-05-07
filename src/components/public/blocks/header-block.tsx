export function HeaderBlock({ data }: { data: Record<string, unknown> }) {
  const title = typeof data.title === "string" ? data.title : "";
  const subtitle = typeof data.subtitle === "string" ? data.subtitle : "";
  return (
    <div className="space-y-1 px-2 text-center">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="text-sm opacity-70">{subtitle}</p>}
    </div>
  );
}
