"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toaster";

const schema = z.object({
  email: z.string().email(),
  username: z
    .string()
    .min(3)
    .max(32)
    .regex(/^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$/, "Letters, digits and hyphens only"),
  password: z.string().min(8, "Use at least 8 characters").max(256),
  name: z.string().min(1).max(64).optional(),
});

type FormValues = z.infer<typeof schema>;

export function RegisterForm() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    setPending(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(values),
      });
      const json = await res.json();
      if (!res.ok || json.ok === false) {
        toast({
          variant: "destructive",
          title: "Couldn't create account",
          description: json?.message ?? "Please review the form and try again.",
        });
        return;
      }
      const signed = await signIn("credentials", {
        email: values.email,
        password: values.password,
        redirect: false,
      });
      if (signed?.error) {
        toast({ title: "Account created", description: "Please sign in to continue." });
        router.push("/login");
      } else {
        router.replace("/dashboard");
        router.refresh();
      }
    } finally {
      setPending(false);
    }
  });

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input id="name" {...register("name")} placeholder="Maya R." />
      </div>
      <div className="space-y-2">
        <Label htmlFor="username">Username</Label>
        <div className="flex">
          <span className="inline-flex items-center rounded-l-md border border-r-0 bg-muted px-3 text-sm text-muted-foreground">
            linkforge.app/u/
          </span>
          <Input id="username" className="rounded-l-none" {...register("username")} placeholder="mayar" />
        </div>
        {errors.username && <p className="text-xs text-destructive">{errors.username.message}</p>}
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="email" {...register("email")} />
        {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
        {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
      </div>
      <Button type="submit" className="w-full" variant="accent" disabled={pending}>
        {pending && <Loader2 className="mr-2 size-4 animate-spin" />}
        Create account
      </Button>
    </form>
  );
}
