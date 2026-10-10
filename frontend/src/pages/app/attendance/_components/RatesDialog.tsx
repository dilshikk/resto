import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Settings, X } from "lucide-react";
import {
  fetchAttendanceEmployees,
  fetchAttendanceRates,
  upsertAttendanceRate,
  type AttendanceRate,
} from "@/api/attendance.ts";
import { cn } from "@/lib/utils.ts";

const CURRENCIES = ["UZS", "USD", "RUB"];

export default function RatesDialog() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  // Список сотрудников из FaceID (для отображения FaceID-имён)
  const { data: employees = [] } = useQuery({
    queryKey: ["attendance-employees"],
    queryFn: fetchAttendanceEmployees,
    enabled: open,
  });

  // Список ставок из основной БД (содержат display_name)
  const { data: rates = [], isLoading } = useQuery({
    queryKey: ["attendance-rates"],
    queryFn: fetchAttendanceRates,
    enabled: open,
  });

  // Карта FaceID-имён по employee_id
  const faceidNameMap: Record<string, string> = {};
  for (const emp of employees) {
    const name = [emp.first_name, emp.last_name].filter(Boolean).join(" ");
    if (name) faceidNameMap[emp.employee_id] = name;
  }

  // Объединяем: все сотрудники из FaceID + те из ставок, кого нет в FaceID
  const allIds = [
    ...new Set([
      ...employees.map((e) => e.employee_id),
      ...rates.map((r) => r.faceid_employee_id),
    ]),
  ];

  const ratesMap: Record<string, AttendanceRate> = {};
  for (const r of rates) ratesMap[r.faceid_employee_id] = r;

  const onSaved = () => {
    void qc.invalidateQueries({ queryKey: ["attendance-employees"] });
    void qc.invalidateQueries({ queryKey: ["attendance-rates"] });
    void qc.invalidateQueries({ queryKey: ["attendance-payroll"] });
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
      >
        <Settings className="h-4 w-4" />
        Ставки
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-xl bg-background shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold">Ставки сотрудников</h2>
                <p className="text-sm text-muted-foreground">
                  Оплата за час. Имя в табеле можно переопределить — оно будет
                  использоваться вместо имени из FaceID.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="cursor-pointer rounded-lg p-1.5 hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Column headers */}
            <div className="grid grid-cols-[1fr_1fr_auto_auto_auto] gap-2 border-b bg-muted/40 px-6 py-2 text-xs font-semibold text-muted-foreground">
              <span>Имя в FaceID</span>
              <span>Имя в табеле</span>
              <span className="w-28 text-right">Ставка/час</span>
              <span className="w-14 text-center">Валюта</span>
              <span className="w-20" />
            </div>

            {/* Content */}
            <div className="max-h-[55vh] overflow-y-auto px-6 py-3">
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              ) : allIds.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">Нет сотрудников</p>
              ) : (
                <div className="space-y-1.5">
                  {allIds.map((id) => (
                    <RateRow
                      key={id}
                      employeeId={id}
                      faceidName={faceidNameMap[id] ?? null}
                      rate={ratesMap[id] ?? null}
                      onSaved={onSaved}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="border-t px-6 py-4">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="cursor-pointer rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Готово
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function RateRow({
  employeeId,
  faceidName,
  rate,
  onSaved,
}: {
  employeeId: string;
  faceidName: string | null;
  rate: AttendanceRate | null;
  onSaved: () => void;
}) {
  const [displayName, setDisplayName] = useState(rate?.display_name ?? "");
  const [rateVal, setRateVal] = useState(String(rate?.rate_per_shift ?? ""));
  const [currency, setCurrency] = useState(rate?.currency ?? "UZS");
  const [saved, setSaved] = useState(false);

  // Если ставка подгрузилась позже (из-за enabled: open) — синхронизируем
  useEffect(() => {
    if (rate) {
      setDisplayName(rate.display_name ?? "");
      setRateVal(String(rate.rate_per_shift || ""));
      setCurrency(rate.currency);
    }
  }, [rate?.faceid_employee_id]);

  const mutation = useMutation({
    mutationFn: () =>
      upsertAttendanceRate(employeeId, {
        // Если display_name не задан — передаём FaceID-имя как начальное значение,
        // чтобы в БД всегда был display_name и смена имени в FaceID не ломала табель
        display_name: displayName.trim() || faceidName || employeeId,
        rate_per_shift: parseFloat(rateVal) || 0,
        currency,
      }),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onSaved();
    },
    onError: () => toast.error("Не удалось сохранить"),
  });

  return (
    <div className="grid grid-cols-[1fr_1fr_auto_auto_auto] items-center gap-2 rounded-lg border px-3 py-2">
      {/* FaceID-имя (только чтение) */}
      <div className="min-w-0">
        <p className="truncate text-sm text-muted-foreground">
          {faceidName ?? <span className="italic">нет данных</span>}
        </p>
        <p className="truncate text-[10px] text-muted-foreground/60">ID: {employeeId}</p>
      </div>

      {/* Имя в табеле (редактируемое, из основной БД) */}
      <input
        type="text"
        value={displayName}
        placeholder={faceidName ?? "Введите имя"}
        onChange={(e) => setDisplayName(e.target.value)}
        className="h-8 min-w-0 rounded-md border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />

      {/* Ставка */}
      <input
        type="number"
        min="0"
        step="500"
        value={rateVal}
        onChange={(e) => setRateVal(e.target.value)}
        placeholder="0"
        className="h-8 w-28 rounded-md border bg-background px-2 text-right text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />

      {/* Валюта */}
      <select
        value={currency}
        onChange={(e) => setCurrency(e.target.value)}
        className="h-8 w-16 cursor-pointer rounded-md border bg-background px-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        {CURRENCIES.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      {/* Сохранить */}
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className={cn(
          "h-8 w-20 cursor-pointer rounded-md px-2 text-sm font-medium transition-colors disabled:opacity-50",
          saved
            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30"
            : "bg-primary text-primary-foreground hover:bg-primary/90",
        )}
      >
        {saved ? "✓ Готово" : mutation.isPending ? "..." : "Сохранить"}
      </button>
    </div>
  );
}
