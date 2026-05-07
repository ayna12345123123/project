export function DividerBlock({ data }: { data: Record<string, unknown> }) {
  const spacing = typeof data.spacing === "number" ? data.spacing : 16;
  return <div style={{ height: spacing }} aria-hidden="true" />;
}
