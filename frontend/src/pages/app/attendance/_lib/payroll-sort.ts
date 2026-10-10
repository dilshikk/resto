import { useState } from "react";
import type { PayrollEmployee } from "@/api/attendance.ts";

export type SortKey = "name" | "position" | "rate";
export type SortDir = "asc" | "desc";
export type PayrollSort = { key: SortKey; dir: SortDir } | null;

const STORAGE_KEY = "attendance-payroll-sort";
const KEYS: readonly string[] = ["name", "position", "rate"];

function isSortKey(value: unknown): value is SortKey {
  return typeof value === "string" && KEYS.includes(value);
}

function readSort(): PayrollSort {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { key?: unknown; dir?: unknown } | null;
    if (parsed && isSortKey(parsed.key) && (parsed.dir === "asc" || parsed.dir === "desc")) {
      return { key: parsed.key, dir: parsed.dir };
    }
  } catch {
    // Повреждённое значение в хранилище - просто игнорируем
  }
  return null;
}

/** Сортировка табеля, запоминается в браузере между заходами. */
export function usePayrollSort() {
  const [sort, setSort] = useState<PayrollSort>(readSort);

  const toggle = (key: SortKey) => {
    const next: PayrollSort =
      sort?.key === key ? { key, dir: sort.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" };
    setSort(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  return { sort, toggle };
}

const collator = new Intl.Collator("ru", { sensitivity: "base", numeric: true });

export function sortEmployees(list: PayrollEmployee[], sort: PayrollSort): PayrollEmployee[] {
  if (!sort) return list;
  const sign = sort.dir === "asc" ? 1 : -1;
  return [...list].sort((a, b) => {
    let diff = 0;
    if (sort.key === "rate") {
      diff = (a.rate_per_hour - b.rate_per_hour) * sign;
    } else if (sort.key === "position") {
      const pa = a.position?.trim() ?? "";
      const pb = b.position?.trim() ?? "";
      // Без должности - всегда в конце списка
      if (!pa !== !pb) return pa ? -1 : 1;
      diff = collator.compare(pa, pb) * sign;
    } else {
      diff = collator.compare(a.name, b.name) * sign;
    }
    return diff || collator.compare(a.name, b.name);
  });
}
