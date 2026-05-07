import { type NextAuthConfig, type DefaultSession } from "next-auth";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";

import { env } from "@/lib/env";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      role: "USER" | "PRO" | "ADMIN" | "SUPPORT";
      username: string;
      twoFactorEnabled: boolean;
    } & DefaultSession["user"];
  }
}

/**
 * Edge-safe auth config — no credentials provider (which would pull in argon2,
 * a Node-only native module).  Used by middleware.ts for session checks at the
 * edge.  The full config in auth.ts re-uses this and adds Credentials.
 */
export const authConfig = {
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  secret: env.AUTH_SECRET,
  trustHost: env.AUTH_TRUST_HOST,
  pages: {
    signIn: "/login",
    error: "/login",
    verifyRequest: "/verify",
  },
  providers: [
    ...(env.AUTH_GOOGLE_ID && env.AUTH_GOOGLE_SECRET
      ? [Google({ clientId: env.AUTH_GOOGLE_ID, clientSecret: env.AUTH_GOOGLE_SECRET })]
      : []),
    ...(env.AUTH_GITHUB_ID && env.AUTH_GITHUB_SECRET
      ? [GitHub({ clientId: env.AUTH_GITHUB_ID, clientSecret: env.AUTH_GITHUB_SECRET })]
      : []),
  ],
  callbacks: {
    async session({ session, token }) {
      const t = token as {
        uid?: string;
        role?: "USER" | "PRO" | "ADMIN" | "SUPPORT";
        username?: string;
        twoFactorEnabled?: boolean;
      };
      if (session.user && t.uid) {
        session.user.id = String(t.uid);
        session.user.role = t.role ?? "USER";
        session.user.username = t.username ?? "";
        session.user.twoFactorEnabled = Boolean(t.twoFactorEnabled);
      }
      return session;
    },
  },
} satisfies NextAuthConfig;
