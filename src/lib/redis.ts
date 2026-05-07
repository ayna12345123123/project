import Redis, { type RedisOptions } from "ioredis";
import { env, isDev } from "./env";

declare global {
  // eslint-disable-next-line no-var
  var __redis: Redis | undefined;
}

const opts: RedisOptions = {
  // BullMQ requires this for blocking commands.
  maxRetriesPerRequest: null,
  enableReadyCheck: true,
  lazyConnect: false,
};

export const redis: Redis =
  globalThis.__redis ?? new Redis(env.REDIS_URL, opts);

if (isDev) globalThis.__redis = redis;
