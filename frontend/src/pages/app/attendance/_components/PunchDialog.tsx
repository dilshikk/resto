import { useState, useEffect } from "react";
import { X } from "lucide-react";
import type { PayrollDay, ShiftFine, ShiftFineKind } from "@/api/attendance.ts";
import { cn } from "@/lib/utils.ts";
import { formatNumber } from "../_lib/utils.ts";

/** Штраф за смену для сохранения; amount 0 - удалить */
export type ShiftFineDraft = {
  kind: ShiftFineKind;
  amount: number;
  planned_start: string | null;
  late_minutes: number | null;
  note: string | null;
};

type Props = {
  employeeName: string;
  date: string;
  day: PayrollDay | undefined;
  saving: boolean;
  /** Подсказка: сумма за минуту опоздания */
  lateFinePerMinute: number;
  /** null = брать время из FaceID */
  onSave: (arrival: string | null, departure: string | null, fines: ShiftFineDraft[]) => void;
  onClose: () => void;
};

const SHIFT_CUTOFF = 6 * 60;

// Минуты от начала смены: ночные часы (до 06:00) идут после 23:59
function shiftMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  const minutes = h * 60 + m;
  return minutes < SHIFT_CUTOFF ? minutes + 24 * 60 : minutes;
}

function lateMinutes(planned: string, arrival: string): number {
  if (!planned || !arrival) return 0;
  return Math.max(0, shiftMinutes(arrival) - shiftMinutes(planned));
}

const parseMoney = (text: string): number => {
  const value = Number(text.replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(value) && value > 0 ? value : 0;
};

const findFine = (day: PayrollDay | undefined, kind: ShiftFineKind): ShiftFine | undefined =>
  day?.fines?.find((f) => f.kind === kind);

// Ручной ввод прихода и ухода за смену + штрафы за смену
export default function PunchDialog({
  employeeName,
  date,
  day,
  saving,
  lateFinePerMinute,
  onSave,
  onClose,
}: Props) {
  const [arrival, setArrival] = useState(day?.arrival ?? "");
  const [departure, setDeparture] = useState(day?.departure ?? "");

  const savedLate = findFine(day, "late");
  const savedAbsence = findFine(day, "absence");
  const [lateOn, setLateOn] = useState(Boolean(savedLate));
  const [plannedStart, setPlannedStart] = useState(savedLate?.planned_start ?? "");
  // null = сумма считается сама по минутам; строка = менеджер ввёл вручную
  const [lateAmountText, setLateAmountText] = useState<string | null>(
    savedLate ? String(savedLate.amount) : null,
  );
  const [lateNote, setLateNote] = useState(savedLate?.note ?? "");
  const [absenceOn, setAbsenceOn] = useState(Boolean(savedAbsence));
  const [absenceAmountText, setAbsenceAmountText] = useState(
    savedAbsence ? String(savedAbsence.amount) : "",
  );
  const [absenceNote, setAbsenceNote] = useState(savedAbsence?.note ?? "");

  // Закрытие диалога по клавише ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const late = lateMinutes(plannedStart, arrival);
  const lateAuto = late * lateFinePerMinute;
  const lateAmount = lateAmountText === null ? lateAuto : parseMoney(lateAmountText);
  const absenceAmount = parseMoney(absenceAmountText);

  const buildFines = (): ShiftFineDraft[] => [
    {
      kind: "late",
      amount: lateOn ? lateAmount : 0,
      planned_start: plannedStart || null,
      late_minutes: late || null,
      note: lateNote.trim() || null,
    },
    {
      kind: "absence",
      amount: absenceOn ? absenceAmount : 0,
      planned_start: null,
      late_minutes: null,
      note: absenceNote.trim() || null,
    },
  ];

  // Если время совпадает с FaceID - не сохраняем как ручное, чтобы не замораживать данные
  const toOverride = (value: string, faceid: string | null | undefined): string | null =>
    value && value !== faceid ? value : null;

  const handleSave = () =>
    onSave(
      toOverride(arrival, day?.faceid_arrival),
      toOverride(departure, day?.faceid_departure),
      buildFines(),
    );

  const finesTotal = (lateOn ? lateAmount : 0) + (absenceOn ? absenceAmount : 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-md flex-col rounded-xl bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold">{employeeName}</h2>
            <p className="text-sm text-muted-foreground">Смена от {date}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-lg p-1.5 hover:bg-muted"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 overflow-y-auto px-5 py-4">
          <TimeField
            label="Приход"
            value={arrival}
            faceid={day?.faceid_arrival ?? null}
            onChange={setArrival}
          />
          <TimeField
            label="Уход"
            value={departure}
            faceid={day?.faceid_departure ?? null}
            onChange={setDeparture}
          />
          <p className="text-xs text-muted-foreground">
            День засчитывается, если указаны и приход, и уход. Ночной уход вводите как
            есть (например 02:00), он останется в дне прихода.
          </p>

          {day?.missing_punch && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
              Автоматический штраф {formatNumber(day.missing_punch_fine ?? 0)}: в FaceID нет
              прихода или ухода. Ручная правка времени его не отменяет.
            </p>
          )}

          {/* Штрафы за смену */}
          <div className="space-y-3 border-t pt-4">
            <div className="flex items-baseline justify-between">
              <h3 className="text-sm font-semibold">Штрафы за смену</h3>
              {finesTotal > 0 && (
                <span className="text-sm font-semibold text-red-600">
                  −{formatNumber(finesTotal)}
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <ToggleChip active={lateOn} onClick={() => setLateOn((v) => !v)}>
                Опоздание
              </ToggleChip>
              <ToggleChip active={absenceOn} onClick={() => setAbsenceOn((v) => !v)}>
                Невыход на смену
              </ToggleChip>
            </div>

            {lateOn && (
              <div className="space-y-2 rounded-lg border p-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="mb-1 block text-xs font-medium">Должен был прийти</label>
                    <input
                      type="time"
                      value={plannedStart}
                      onChange={(e) => setPlannedStart(e.target.value)}
                      className="h-9 w-full rounded-lg border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium">Сумма штрафа</label>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={lateAmountText ?? (lateAuto ? String(lateAuto) : "")}
                      placeholder="0"
                      onChange={(e) => setLateAmountText(e.target.value)}
                      className="h-9 w-full rounded-lg border bg-background px-2 text-right text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  {plannedStart && arrival
                    ? late > 0
                      ? `Опоздал на ${late} мин × ${formatNumber(lateFinePerMinute)} = ${formatNumber(lateAuto)}`
                      : "Пришёл вовремя"
                    : "Укажите, во сколько должен был прийти - минуты посчитаются сами"}
                  {lateAmountText !== null && lateAmount !== lateAuto && (
                    <button
                      type="button"
                      onClick={() => setLateAmountText(null)}
                      className="ml-2 cursor-pointer text-primary underline"
                    >
                      по минутам
                    </button>
                  )}
                </p>
                <NoteInput value={lateNote} onChange={setLateNote} />
              </div>
            )}

            {absenceOn && (
              <div className="space-y-2 rounded-lg border p-3">
                <div>
                  <label className="mb-1 block text-xs font-medium">Сумма штрафа</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={absenceAmountText}
                    placeholder="Например 100000"
                    onChange={(e) => setAbsenceAmountText(e.target.value)}
                    className="h-9 w-full rounded-lg border bg-background px-2 text-right text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <NoteInput value={absenceNote} onChange={setAbsenceNote} />
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t px-5 py-4">
          <button
            type="button"
            onClick={() => onSave(null, null, buildFines())}
            disabled={saving || !day?.manual}
            className="cursor-pointer rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            Вернуть FaceID
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="cursor-pointer rounded-lg px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Сохранение…" : "Сохранить"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "cursor-pointer rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300"
          : "hover:bg-muted",
      )}
    >
      {active ? "✓ " : "+ "}
      {children}
    </button>
  );
}

function NoteInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="text"
      value={value}
      maxLength={255}
      placeholder="Комментарий (необязательно)"
      onChange={(e) => onChange(e.target.value)}
      className="h-9 w-full rounded-lg border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
    />
  );
}

function TimeField({
  label,
  value,
  faceid,
  onChange,
}: {
  label: string;
  value: string;
  faceid: string | null;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <label className="text-sm font-medium">{label}</label>
        <span className="text-xs text-muted-foreground">FaceID: {faceid ?? "нет"}</span>
      </div>
      <input
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
    </div>
  );
}
