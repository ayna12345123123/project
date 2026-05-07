export function TextBlock({ data }: { data: Record<string, unknown> }) {
  const text = typeof data.text === "string" ? data.text : "";
  const align = (data.align as string) ?? "left";
  return (
    <div
      className="px-2 text-sm leading-relaxed opacity-90"
      style={{ textAlign: align as React.CSSProperties["textAlign"] }}
    >
      {text}
    </div>
  );
}
