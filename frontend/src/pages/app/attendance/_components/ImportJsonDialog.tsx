import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { toast } from "sonner";
import { FileJson, X } from "lucide-react";
import { importFaceidJson, type ImportJsonResult } from "@/api/attendance-import.ts";

// Проверяет, что вставлен ответ терминала: { AcsEvent: { InfoList: [...] } }
function parseTerminalJson(raw: string): object | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || !("AcsEvent" in parsed)) return null;
    const acs = parsed.AcsEvent;
    if (typeof acs !== "object" || acs === null || !("InfoList" in acs)) return null;
    return Array.isArray(acs.InfoList) ? parsed : null;
  } catch {
    return null;
  }
}

function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (error.response?.status === 403) return "Нужны права менеджера";
    if (error.response?.status === 503) return "База FaceID не подключена";
  }
  return "Не удалось импортировать данные";
}

export default function ImportJsonDialog() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [result, setResult] = useState<ImportJsonResult | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ payload, overrideId }: { payload: object; overrideId?: string }) =>
      importFaceidJson(payload, overrideId),
    onSuccess: (data) => {
      setResult(data);
      if (data.unmapped_hashes.length === 0) {
        setText("");
        setEmployeeId("");
      }
      void qc.invalidateQueries({ queryKey: ["attendance-payroll"] });
      void qc.invalidateQueries({ queryKey: ["attendance-employees"] });
      toast.success(`Добавлено отметок: ${data.inserted}`);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const handleImport = () => {
    const payload = parseTerminalJson(text.trim());
    if (!payload) {
      toast.error("Это не похоже на ответ терминала. Вставьте JSON целиком, вместе с AcsEvent.");
      return;
    }
    setResult(null);
    mutation.mutate({ payload, overrideId: employeeId.trim() || undefined });
  };

  const close = () => {
    setOpen(false);
    setResult(null);
    setEmployeeId("");
  };

  const needsEmployeeId = (result?.unmapped_hashes.length ?? 0) > 0;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
      >
        <FileJson className="h-4 w-4" />
        Импорт JSON
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-xl bg-background shadow-2xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold">Импорт отметок из JSON</h2>
                <p className="text-sm text-muted-foreground">
                  Вставьте ответ терминала FaceID. Новые отметки сразу попадут в базу, повторы
                  (тот же сотрудник, дата и минута) пропускаются.
                </p>
              </div>
              <button
                type="button"
                onClick={close}
                className="cursor-pointer rounded-lg p-1.5 hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 px-6 py-4">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={'{ "AcsEvent": { "InfoList": [ ... ] } }'}
                rows={10}
                spellCheck={false}
                className="w-full resize-y rounded-lg border bg-background p-3 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              />

              {needsEmployeeId && (
                <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/40">
                  <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                    Терминал зашифровал ID сотрудника в {result?.unmapped_hashes.length}{" "}
                    {result?.unmapped_hashes.length === 1 ? "отметке" : "отметках"}. Укажите, какому
                    сотруднику они принадлежат, и нажмите «Импортировать» ещё раз — учитывается
                    только время прихода/ухода, остальные данные не используются.
                  </p>
                  <input
                    value={employeeId}
                    onChange={(e) => setEmployeeId(e.target.value)}
                    placeholder="ID сотрудника (например 1036440268)"
                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              )}

              {result && <ImportSummary result={result} />}
            </div>

            <div className="flex gap-2 border-t px-6 py-4">
              <button
                type="button"
                onClick={handleImport}
                disabled={
                  !text.trim() ||
                  mutation.isPending ||
                  (needsEmployeeId && !employeeId.trim())
                }
                className="cursor-pointer rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {mutation.isPending ? "Импортирую..." : "Импортировать"}
              </button>
              <button
                type="button"
                onClick={close}
                className="cursor-pointer rounded-lg px-4 py-2 text-sm font-medium hover:bg-muted"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ImportSummary({ result }: { result: ImportJsonResult }) {
  const period =
    result.date_from && result.date_to
      ? result.date_from === result.date_to
        ? result.date_from
        : `${result.date_from} — ${result.date_to}`
      : null;

  return (
    <div className="space-y-1 rounded-lg border bg-muted/40 p-4 text-sm">
      <p>
        Событий в JSON: <b>{result.total}</b>
        {period && <span className="text-muted-foreground"> (период {period})</span>}
      </p>
      <p className="text-emerald-600">Добавлено в базу: <b>{result.inserted}</b></p>
      <p className="text-muted-foreground">Уже были в базе или повторы: {result.duplicates}</p>
      {result.skipped > 0 && (
        <div className="text-amber-600">
          <p>Пропущено: {result.skipped}</p>
          <ul className="list-inside list-disc text-xs">
            {result.skipped_reasons.map((r) => (
              <li key={r.reason}>
                {r.reason}: {r.count}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
