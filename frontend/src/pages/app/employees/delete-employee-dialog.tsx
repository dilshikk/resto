import type { Employee } from "@/api/employees.ts";

export default function DeleteEmployeeDialog({
  employee,
  onClose,
  onConfirm,
  submitting,
}: {
  employee: Employee;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  submitting: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Удалить сотрудника</h2>
          <button type="button" onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-muted-foreground">
            Сотрудник <strong>{employee.full_name}</strong> будет удалён, а его Telegram отвязан.
            Когда он снова напишет боту, начнётся новая регистрация.
          </p>
          <p className="text-xs text-muted-foreground">
            Если у сотрудника есть история (чек-листы, фото, отчёты), запись останется в архиве,
            чтобы не испортить отчёты, но с Telegram и веб-аккаунтом она больше не связана.
          </p>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="cursor-pointer rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={submitting}
              className="cursor-pointer rounded-lg bg-destructive px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? "Удаляем..." : "Удалить"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
