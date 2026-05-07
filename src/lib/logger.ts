import pino from "pino";
import { env, isDev } from "./env";

export const logger = pino({
  level: env.LOG_LEVEL,
  transport: isDev
    ? {
        target: "pino-pretty",
        options: { colorize: true, translateTime: "SYS:standard" },
      }
    : undefined,
  redact: {
    paths: [
      "req.headers.authorization",
      "req.headers.cookie",
      "*.password",
      "*.passwordHash",
      "*.refreshToken",
    ],
    censor: "[REDACTED]",
  },
});
