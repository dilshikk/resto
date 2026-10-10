# Разовые импорты данных

Файлы в этой папке НЕ применяются автоматически сервисом `migrate`.
Они предназначены для отдельной базы FaceID (`ATTENDANCE_DATABASE_URL`).

## faceid_2026-09-30_2026-10-10.sql

Отметки прихода/ухода из Excel «Транзакции_2026-09-30_2026-10-10.xlsx» -> `public.access_logs`.

- «Идентификатор» -> `employee_id`
- «Дата» + «Время» -> `access_date`, `access_time`, `access_datetime` (время Asia/Tashkent)
- «Регистрация входа» -> `direction = 'in'`, «Регистрация выхода» -> `direction = 'out'`
- Имя -> `first_name` / `last_name`
- `auth_type = 'excel_import'`, `device_name = 'Excel import'` (чтобы импорт можно было найти и при необходимости удалить)
- Точные повторы из Excel удалены (1471 -> 1128 строк). Отметка пропускается, если в базе уже есть событие у этого сотрудника в ту же дату и минуту, поэтому повторный запуск ничего не дублирует.
- Весь файл выполняется в одной транзакции: при ошибке ничего не записывается.

Запуск (строка подключения — как в `ATTENDANCE_DATABASE_URL`, но без `+asyncpg`):

```bash
psql "postgresql://user:pass@host:5432/faceid_db" -v ON_ERROR_STOP=1 \
  -f backend/imports/faceid_2026-09-30_2026-10-10.sql
```

Откат импорта:

```sql
DELETE FROM public.access_logs WHERE auth_type = 'excel_import';
```
