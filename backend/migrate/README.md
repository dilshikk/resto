# Миграции базы данных (Docker)

Сервис `migrate` применяет все файлы `backend/migrations/*.sql` по порядку
(001, 002, ...) и записывает каждый применённый файл в таблицу
`schema_migrations`. Повторно файл не применяется.

## Как это работает

- При `docker compose up -d --build` сначала стартует `db`, затем `migrate`,
  и только после его успешного завершения — `backend`.
- Работает и на новой (пустой) базе, и на уже существующей.

## Команды

```bash
# Применить новые миграции вручную
docker compose run --rm migrate

# Посмотреть, какие миграции уже применены
docker compose exec db psql -U mado -d mado_checklist \
  -c "SELECT filename, applied_at FROM schema_migrations ORDER BY filename;"
```

## Как добавить новую миграцию

1. Создайте файл со следующим номером, например `021_something.sql`.
2. Пишите идемпотентный SQL (`IF NOT EXISTS`, `IF EXISTS`, проверки через `pg_constraint`).
3. Не изменяйте уже применённые файлы — создавайте новый.
4. Выполните `docker compose up -d --build` (или `docker compose run --rm migrate`).
