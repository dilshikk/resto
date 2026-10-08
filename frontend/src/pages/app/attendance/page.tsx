import { useState } from "react";
import { cn } from "@/lib/utils.ts";
import RatesDialog from "./_components/RatesDialog.tsx";
import PayrollTab from "./_components/PayrollTab.tsx";
import LogsTab from "./_components/LogsTab.tsx";

type Tab = "payroll" | "logs";

const TABS: { id: Tab; label: string }[] = [
  { id: "payroll", label: "Табель и зарплата" },
  { id: "logs", label: "Журнал событий" },
];

export default function AttendancePage() {
  const [tab, setTab] = useState<Tab>("payroll");

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Посещаемость (FaceID)</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Учёт посещаемости сотрудников и расчёт зарплаты
          </p>
        </div>
        <RatesDialog />
      </div>

      <div className="inline-flex gap-1 rounded-lg bg-secondary p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "cursor-pointer rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              tab === t.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "payroll" ? <PayrollTab /> : <LogsTab />}
    </div>
  );
}
