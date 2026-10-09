/** Часы с точностью до сотых: 565 минут -> "9,42". */
export function formatHours(minutes: number): string {
  if (minutes <= 0) return "0";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(minutes / 60);
}
