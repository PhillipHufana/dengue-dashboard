"use client";

function toNum(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function formatCases(value: unknown): string {
  const n = Math.round(toNum(value));
  return n.toLocaleString();
}

export function formatRate(value: unknown): string {
  return toNum(value).toFixed(1);
}

export function formatSurgeX(value: unknown): string {
  return `${toNum(value).toFixed(1)}x`;
}

export function formatCaseRange(low: unknown, high: unknown): string {
  return `${Math.round(toNum(low)).toLocaleString()}-${Math.round(toNum(high)).toLocaleString()}`;
}

