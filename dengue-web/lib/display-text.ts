"use client";

export function humanizeName(value: string | null | undefined): string {
  if (!value) return "";
  return String(value)
    .replace(/_/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => {
      if (/^\d+[a-z]$/i.test(part)) return part.toUpperCase();
      return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    })
    .join(" ");
}

export function humanizeClass(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return String(value)
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

export function formatReadableDate(value?: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function formatDateRange(start?: string | null, end?: string | null): string {
  const s = formatReadableDate(start);
  const e = formatReadableDate(end);
  if (s && e) return `${s} - ${e}`;
  return s || e || "-";
}
