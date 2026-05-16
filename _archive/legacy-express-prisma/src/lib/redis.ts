import { createClient } from "redis";

const redisUrl = process.env.REDIS_URL;

export const redis = redisUrl
  ? createClient({ url: redisUrl })
  : null;

let connected = false;

export async function ensureRedis() {
  if (!redis || connected) return;
  await redis.connect();
  connected = true;
}

export async function getCache<T>(key: string): Promise<T | null> {
  if (!redis) return null;
  await ensureRedis();
  const raw = await redis.get(key);
  if (!raw) return null;
  return JSON.parse(raw) as T;
}

export async function setCache(key: string, value: unknown, ttlSeconds = 30) {
  if (!redis) return;
  await ensureRedis();
  await redis.set(key, JSON.stringify(value), { EX: ttlSeconds });
}

export async function invalidateByPrefix(prefix: string) {
  if (!redis) return;
  await ensureRedis();
  const keys = await redis.keys(`${prefix}*`);
  if (keys.length > 0) {
    await redis.del(keys);
  }
}
