-- 021: allow deleting employees without breaking history.
-- Every foreign key that points to employees(id) and currently blocks deletion
-- (NO ACTION / RESTRICT) is recreated with ON DELETE SET NULL (if the column
-- is nullable) or ON DELETE CASCADE (if the column is NOT NULL).
-- employee_accounts are always cascaded. Safe to run multiple times.

BEGIN;

DO $$
DECLARE
    r record;
    col_nullable boolean;
    action text;
BEGIN
    FOR r IN
        SELECT c.conname,
               c.conrelid::regclass AS tbl,
               a.attname           AS col,
               a.attnotnull        AS notnull
        FROM pg_constraint c
        JOIN pg_attribute a
          ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
        WHERE c.contype = 'f'
          AND c.confrelid = 'employees'::regclass
          AND array_length(c.conkey, 1) = 1
          AND c.confdeltype IN ('a', 'r')
    LOOP
        IF r.tbl::text = 'employee_accounts' OR r.notnull THEN
            action := 'CASCADE';
        ELSE
            action := 'SET NULL';
        END IF;

        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES employees(id) ON DELETE %s',
            r.tbl, r.conname, r.col, action
        );
        RAISE NOTICE '%.% -> ON DELETE %', r.tbl, r.col, action;
    END LOOP;
END $$;

COMMIT;
