import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { z } from "zod";
import argon2 from "argon2";

import { prisma } from "@/lib/prisma";
import { rateLimit } from "@/lib/rate-limit";
import { logger } from "@/lib/logger";
import { authConfig } from "@/auth.config";

const credsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(256),
});

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(prisma),
  providers: [
    ...authConfig.providers,
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(input) {
        const parsed = credsSchema.safeParse(input);
        if (!parsed.success) return null;
        const { email, password } = parsed.data;

        // Per-email rate-limit (IP-based limit is enforced separately in the
        // route handler — Auth.js doesn't expose the request here).
        const rl = await rateLimit(`auth:login:${email.toLowerCase()}`, 10, 30);
        if (!rl.ok) {
          logger.warn({ email }, "auth.login.rate_limited");
          return null;
        }

        const user = await prisma.user.findUnique({
          where: { email: email.toLowerCase() },
        });
        if (!user || !user.passwordHash || user.deletedAt) return null;

        const ok = await argon2.verify(user.passwordHash, password);
        if (!ok) return null;

        await prisma.user.update({
          where: { id: user.id },
          data: { lastSeenAt: new Date() },
        });

        return {
          id: user.id,
          email: user.email,
          name: user.name ?? user.username,
          image: user.avatarUrl ?? null,
        };
      },
    }),
  ],
  callbacks: {
    ...authConfig.callbacks,
    async jwt({ token, user, trigger }) {
      if (user?.id) {
        token.uid = user.id;
      }
      if (token.uid && (trigger === "signIn" || trigger === "update" || !token.role)) {
        const dbUser = await prisma.user.findUnique({
          where: { id: String(token.uid) },
          select: { role: true, username: true, twoFactorEnabled: true },
        });
        if (dbUser) {
          token.role = dbUser.role;
          token.username = dbUser.username;
          token.twoFactorEnabled = dbUser.twoFactorEnabled;
        }
      }
      return token;
    },
  },
  events: {
    async signIn({ user, account }) {
      logger.info({ userId: user?.id, provider: account?.provider }, "auth.signIn");
    },
    async signOut(message) {
      logger.info({ message }, "auth.signOut");
    },
  },
});
