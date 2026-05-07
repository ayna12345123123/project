export function FaqBlock({ data }: { data: Record<string, unknown> }) {
  const items = Array.isArray(data.items) ? (data.items as { q: string; a: string }[]) : [];
  return (
    <div className="rounded-[var(--lf-radius)] bg-[color:var(--lf-surface)] p-4 ring-1 ring-current/10">
      <ul className="divide-y divide-current/10">
        {items.map((it, i) => (
          <li key={i} className="py-3">
            <details className="group">
              <summary className="flex cursor-pointer items-center justify-between text-sm font-medium">
                {it.q}
                <span className="ml-2 text-xs opacity-60 transition group-open:rotate-180">▾</span>
              </summary>
              <p className="mt-2 text-sm opacity-80">{it.a}</p>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}
