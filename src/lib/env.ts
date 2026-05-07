/**
 * Centralised, zod-typed runtime environment.
 *
 * Every other module imports `env` from here so we have one place to validate
 * and document required variables.  Validation runs once at module load; in
 * production a missing required variable will crash the process at boot.
 */
import { z } from "zod";

const stringFlag = z
  .union([z.literal("true"), z.literal("false"), z.literal("1"), z.literal("0")])
  .transform((v) => v === "true" || v === "1")
  .or(z.boolean())
  .default(false);

const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  APP_URL: z.string().url().default("http://localhost:3000"),
  APP_NAME: z.string().default("Linkforge"),
  PORT: z.coerce.number().int().positive().default(3000),

  DATABASE_URL: z.string().min(1),
  REDIS_URL: z.string().min(1).default("redis://localhost:6379"),

  AUTH_SECRET: z.string().min(16),
  AUTH_TRUST_HOST: stringFlag,
  AUTH_GOOGLE_ID: z.string().optional().default(""),
  AUTH_GOOGLE_SECRET: z.string().optional().default(""),
  AUTH_GITHUB_ID: z.string().optional().default(""),
  AUTH_GITHUB_SECRET: z.string().optional().default(""),

  EMAIL_FROM: z.string().optional().default(""),
  SMTP_HOST: z.string().optional().default(""),
  SMTP_PORT: z.coerce.number().int().positive().default(587),
  SMTP_USER: z.string().optional().default(""),
  SMTP_PASSWORD: z.string().optional().default(""),

  TELEGRAM_BOT_TOKEN: z.string().optional().default(""),
  TELEGRAM_BOT_USERNAME: z.string().optional().default(""),

  S3_ENDPOINT: z.string().optional().default(""),
  S3_REGION: z.string().default("auto"),
  S3_BUCKET: z.string().default("linkforge-assets"),
  S3_ACCESS_KEY: z.string().optional().default(""),
  S3_SECRET_KEY: z.string().optional().default(""),
  S3_PUBLIC_URL: z.string().optional().default(""),

  STRIPE_SECRET_KEY: z.string().optional().default(""),
  STRIPE_WEBHOOK_SECRET: z.string().optional().default(""),
  STRIPE_PRICE_PRO_MONTHLY: z.string().optional().default(""),
  STRIPE_PRICE_PRO_YEARLY: z.string().optional().default(""),
  NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY: z.string().optional().default(""),

  OPENAI_API_KEY: z.string().optional().default(""),
  OPENAI_BASE_URL: z.string().default("https://api.openai.com/v1"),
  OPENAI_MODEL: z.string().default("gpt-4o-mini"),

  MAXMIND_LICENSE_KEY: z.string().optional().default(""),

  LOG_LEVEL: z.enum(["fatal", "error", "warn", "info", "debug", "trace"]).default("info"),
  SENTRY_DSN: z.string().optional().default(""),

  TRUSTED_ORIGINS: z.string().optional().default(""),
  RATE_LIMIT_WRITES_PER_MIN: z.coerce.number().int().positive().default(60),
  RATE_LIMIT_PUBLIC_VIEWS_PER_MIN: z.coerce.number().int().positive().default(600),

  FEATURE_AI: stringFlag,
  FEATURE_BILLING: stringFlag,
  FEATURE_CUSTOM_DOMAINS: stringFlag,
});

export type Env = z.infer<typeof schema>;

const parsed = schema.safeParse(process.env);

if (!parsed.success) {
  // eslint-disable-next-line no-console
  console.error(
    "❌ Invalid environment variables:",
    parsed.error.flatten().fieldErrors,
  );
  throw new Error("Invalid environment variables");
}

export const env: Env = parsed.data;

export const isProd = env.NODE_ENV === "production";
export const isDev = env.NODE_ENV === "development";
