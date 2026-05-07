/**
 * Token-bucket rate-limit on Redis.  Atomic via a small Lua script.  Returns
 * { ok, remaining, resetAt } so callers can set X-RateLimit headers.
 */
import { redis } from "./redis";

const SCRIPT = `
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_min = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'updated')
local tokens = tonumber(data[1])
local updated = tonumber(data[2])

if tokens == nil then
  tokens = capacity
  updated = now
end

local elapsed_ms = math.max(0, now - updated)
local refill = (refill_per_min * elapsed_ms) / 60000.0
tokens = math.min(capacity, tokens + refill)

local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'updated', now)
redis.call('PEXPIRE', key, 120000)

local reset_at = now + ((1 - tokens) / refill_per_min) * 60000
return { allowed, math.floor(tokens), math.floor(reset_at) }
`;

export type RateLimitResult = {
  ok: boolean;
  remaining: number;
  resetAt: number;
};

export async function rateLimit(
  bucket: string,
  capacity: number,
  perMinute: number,
): Promise<RateLimitResult> {
  const key = `rl:${bucket}`;
  const now = Date.now();
  // ioredis types `eval` as accepting (script, numKeys, ...keysAndArgs)
  const res = (await redis.eval(
    SCRIPT,
    1,
    key,
    String(capacity),
    String(perMinute),
    String(now),
  )) as [number, number, number];
  return {
    ok: res[0] === 1,
    remaining: res[1] ?? 0,
    resetAt: res[2] ?? now,
  };
}
