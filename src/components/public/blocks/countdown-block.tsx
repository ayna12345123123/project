"use client";

import { useEffect, useState } from "react";

function diff(target: number) {
  const ms = Math.max(0, target - Date.now());
  const sec = Math.floor(ms / 1000) % 60;
  const min = Math.floor(ms / 60_000) % 60;
  const hrs = Math.floor(ms / 3_600_000) % 24;
  const days = Math.floor(ms / 86_400_000);
  return { days, hrs, min, sec, finished: ms === 0 };
}

export function CountdownBlock({ data }: { data: Record<string, unknown> }) {
  const targetAt = typeof data.targetAt === "string" ? Date.parse(data.targetAt) : NaN;
  const [now, setNow] = useState(() => diff(targetAt));
  useEffect(() => {
    if (Number.isNaN(targetAt)) return;
    const id = setInterval(() => setNow(diff(targetAt)), 1000);
    return () => clearInterval(id);
  }, [targetAt]);

  if (Number.isNaN(targetAt)) return null;

  if (now.finished) {
    const finishedText = typeof data.finishedText === "string" ? data.finishedText : "We're live!";
    return (
      <div className="rounded-[var(--lf-radius)] bg-[color:var(--lf-surface)] p-6 text-center text-sm font-semibold ring-1 ring-current/10">
        {finishedText}
      </div>
    );
  }

  const cells = [
    { v: now.days, l: "days" },
    { v: now.hrs, l: "hrs" },
    { v: now.min, l: "min" },
    { v: now.sec, l: "sec" },
  ];
  return (
    <div className="grid grid-cols-4 gap-2 rounded-[var(--lf-radius)] bg-[color:var(--lf-surface)] p-4 ring-1 ring-current/10">
      {cells.map((c) => (
        <div key={c.l} className="text-center">
          <div className="text-xl font-semibold tabular-nums">{String(c.v).padStart(2, "0")}</div>
          <div className="text-[10px] uppercase opacity-60">{c.l}</div>
        </div>
      ))}
    </div>
  );
}
