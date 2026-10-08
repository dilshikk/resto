import { useState } from "react";
import { X } from "lucide-react";
import type { PayrollDay } from "@/api/attendance.ts";

type Props = {
  employeeName: string;
  date: string;
  day: PayrollDay | undefined;
  saving: boolean;
  /** null = брать время из FaceID */
  onSave: (arrival: string | null, departure: string | null) => void;
  onClose: () => void;
};

// Ручной ввод прихода и ухода за смену
export default function PunchDialog({ employeeName, date, day, saving, onSave, onClose }: Props) {
  const [arrival, setArrival] = useState(day?.arrival ?? "");
  const [departure, setDeparture] = useState(day?.departure ?? "");

  // Если время совпадает с FaceID - не сохраняем как ручное, чтобы не замораживать данные
  const toOverride = (value: string, faceid: string | null | undefined): string | null =>
    value && value !== faceid ? value : null;

  const handleSave = () =>
    onSave(toOverride(arrival, day?.faceid_arrival), toOverride(departure, day?.faceid_departure));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-xl bg-background shadow-2xl"
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

        <div className="space-y-4 px-5 py-4">
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
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t px-5 py-4">
          <button
            type="button"
            onClick={() => onSave(null, null)}
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
              {saving ? "..." : "Сохранить"}
            </button>
          </div>
        </div>
      </div>
    </div>
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
