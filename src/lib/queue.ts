/**
 * BullMQ queues — defined in one place so both the web process and the worker
 * process import the exact same queue names + options.
 */
import { Queue, type JobsOptions } from "bullmq";
import { env } from "./env";

const connection = { url: env.REDIS_URL };

const defaultJobOptions: JobsOptions = {
  attempts: 5,
  backoff: { type: "exponential", delay: 1000 },
  removeOnComplete: { age: 3600, count: 1000 },
  removeOnFail: { age: 7 * 24 * 3600 },
};

export const QUEUE_NAMES = {
  imageProcess: "image-process",
  analyticsRollup: "analytics-rollup",
  emailSend: "email-send",
  aiGenerate: "ai-generate",
  webhookDeliver: "webhook-deliver",
} as const;

export type QueueName = (typeof QUEUE_NAMES)[keyof typeof QUEUE_NAMES];

const queues = new Map<QueueName, Queue>();

export function getQueue(name: QueueName): Queue {
  let q = queues.get(name);
  if (!q) {
    q = new Queue(name, { connection, defaultJobOptions });
    queues.set(name, q);
  }
  return q;
}

export const trackEvent = (payload: Record<string, unknown>) =>
  getQueue(QUEUE_NAMES.analyticsRollup).add("track", payload, {
    removeOnComplete: true,
  });
