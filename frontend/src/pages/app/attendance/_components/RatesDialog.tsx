import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Settings, X } from "lucide-react";
import {
  fetchAttendanceEmployees,
  upsertAttendanceRate,
  type AttendanceEmployee,
} from "@/api/attendance.ts";
import { cn } from "@/lib/utils.ts";

const CURRENCIES = ["UZS", "USD", "RUB"];

export default function RatesDialog() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const { data: employees = [], isLoading } = useQuery({
    queryKey: ["attendance-employees"],
    queryFn: fetchAttendanceEmployees,
    enabled: open,
  });

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
                  Оплата за один час. Ставку также можно менять прямо в табеле.
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

            {/* Content */}
            <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              ) : employees.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">Нет сотрудников</p>
              ) : (
                <div className="space-y-2">
                  {employees.map((emp) => (
                    <RateRow
                      key={emp.employee_id}
                      employee={emp}
                      onSaved={() => {
                        qc.invalidateQueries({ queryKey: ["attendance-employees"] });
                        qc.invalidateQueries({ queryKey: ["attendance-payroll"] });
                      }}
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
  employee,
  onSaved,
}: {
  employee: AttendanceEmployee;
  onSaved: () => void;
}) {
  const [rate, setRate] = useState(String(employee.rate_per_shift ?? ""));
  const [currency, setCurrency] = useState(employee.currency ?? "UZS");
  const [saved, setSaved] = useState(false);

  const fullName =
    [employee.first_name, employee.last_name].filter(Boolean).join(" ") ||
    employee.employee_id;

  const mutation = useMutation({
    mutationFn: () =>
      upsertAttendanceRate(employee.employee_id, {
        display_name: fullName,
        rate_per_shift: parseFloat(rate) || 0,
        currency,
      }),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onSaved();
    },
    onError: () => toast.error("Не удалось сохранить ставку"),
  });

  return (
    <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
      <span className="min-w-0 flex-1 truncate text-sm font-medium">{fullName}</span>
      <input
        type="number"
        min="0"
        step="500"
        value={rate}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRate(e.target.value)}
        placeholder="за час"
        className="h-8 w-32 rounded-md border bg-background px-2 text-right text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <select
        value={currency}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCurrency(e.target.value)}
        className="h-8 rounded-md border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        {CURRENCIES.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className={cn(
          "h-8 cursor-pointer rounded-md px-3 text-sm font-medium transition-colors disabled:opacity-50",
          saved
            ? "bg-emerald-100 text-emerald-700"
            : "bg-primary text-primary-foreground hover:bg-primary/90",
        )}
      >
        {saved ? "✓" : mutation.isPending ? "..." : "Сохранить"}
      </button>
    </div>
  );
}
