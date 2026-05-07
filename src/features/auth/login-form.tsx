"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Github } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toaster";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(256),
});

type FormValues = z.infer<typeof schema>;

export function LoginForm() {
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") ?? "/dashboard";
  const [pending, setPending] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    setPending(true);
    const res = await signIn("credentials", { ...values, redirect: false });
    setPending(false);
    if (res?.error) {
      toast({ variant: "destructive", title: "Sign in failed", description: "Check your credentials and try again." });
      return;
    }
    router.replace(next);
    router.refresh();
  });

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="email" {...register("email")} />
        {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
        {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
      </div>
      <Button type="submit" className="w-full" disabled={pending} variant="accent">
        {pending && <Loader2 className="mr-2 size-4 animate-spin" />}
        Sign in
      </Button>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or continue with
        <span className="h-px flex-1 bg-border" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => signIn("google", { callbackUrl: next })}
        >
          <span className="mr-2">G</span>Google
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => signIn("github", { callbackUrl: next })}
        >
          <Github className="mr-2 size-4" />
          GitHub
        </Button>
      </div>
    </form>
  );
}
