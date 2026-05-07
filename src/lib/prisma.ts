import { PrismaClient } from "@prisma/client";
import { env, isDev } from "./env";

declare global {
  // eslint-disable-next-line no-var
  var __prisma: PrismaClient | undefined;
}

export const prisma: PrismaClient =
  globalThis.__prisma ??
  new PrismaClient({
    log: isDev ? ["warn", "error"] : ["error"],
  });

if (isDev) globalThis.__prisma = prisma;

export type DB = typeof prisma;

// Re-export the env so tests/seed scripts importing prisma get DATABASE_URL
// loaded through the same validation path.
export { env };
