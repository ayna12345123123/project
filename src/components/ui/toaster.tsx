"use client";

import * as React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { create } from "zustand";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "destructive" | "success";

interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastStore {
  items: ToastItem[];
  push: (item: Omit<ToastItem, "id">) => void;
  remove: (id: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  items: [],
  push: (item) =>
    set((s) => ({
      items: [...s.items, { id: Math.random().toString(36).slice(2), ...item }],
    })),
  remove: (id) => set((s) => ({ items: s.items.filter((t) => t.id !== id) })),
}));

export function toast(input: Omit<ToastItem, "id">) {
  useToastStore.getState().push(input);
}

export function Toaster() {
  const items = useToastStore((s) => s.items);
  const remove = useToastStore((s) => s.remove);
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {items.map((t) => (
        <ToastPrimitive.Root
          key={t.id}
          onOpenChange={(open) => !open && remove(t.id)}
          duration={4500}
          className={cn(
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out data-[state=open]:slide-in-from-right-full",
            "pointer-events-auto flex w-80 items-start gap-3 rounded-lg border p-4 shadow-lg",
            t.variant === "destructive"
              ? "border-destructive/50 bg-destructive/10 text-destructive"
              : t.variant === "success"
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border bg-background text-foreground",
          )}
        >
          <div className="flex-1">
            {t.title && <ToastPrimitive.Title className="text-sm font-medium">{t.title}</ToastPrimitive.Title>}
            {t.description && (
              <ToastPrimitive.Description className="mt-1 text-sm opacity-90">
                {t.description}
              </ToastPrimitive.Description>
            )}
          </div>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed bottom-0 right-0 z-[100] m-4 flex max-h-screen w-full max-w-[420px] flex-col gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}
