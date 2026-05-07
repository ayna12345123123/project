/**
 * Tiny helpers for typed JSON API responses (RFC-7807-ish problem details).
 */
import { NextResponse } from "next/server";
import type { ZodIssue } from "zod";

export interface Problem {
  ok: false;
  code: string;
  message: string;
  status: number;
  details?: unknown;
}

export type ApiResponse<T> = { ok: true; data: T } | Problem;

export function ok<T>(data: T, init?: ResponseInit) {
  return NextResponse.json<ApiResponse<T>>({ ok: true, data }, init);
}

export function problem(
  status: number,
  code: string,
  message: string,
  details?: unknown,
) {
  return NextResponse.json<Problem>(
    { ok: false, code, message, status, details },
    { status },
  );
}

export const errors = {
  badRequest: (message: string, details?: ZodIssue[] | unknown) =>
    problem(400, "BAD_REQUEST", message, details),
  unauthorized: (message = "Authentication required") =>
    problem(401, "UNAUTHORIZED", message),
  forbidden: (message = "Forbidden") => problem(403, "FORBIDDEN", message),
  notFound: (message = "Not found") => problem(404, "NOT_FOUND", message),
  conflict: (message = "Conflict") => problem(409, "CONFLICT", message),
  tooMany: (message = "Too many requests") =>
    problem(429, "RATE_LIMITED", message),
  internal: (message = "Internal server error") =>
    problem(500, "INTERNAL", message),
} as const;
