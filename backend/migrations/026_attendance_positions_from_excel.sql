-- 026: должности сотрудников FaceID из Excel «Транзакции_2026-09-30_2026-10-10.xlsx» (колонка «Позиция»).
-- Применяется к ОСНОВНОЙ базе (mado_checklist) автоматически сервисом migrate.
-- Заполняет только тех, у кого должность ещё не указана: ручные правки в табеле не затираются.
-- Повторный запуск безопасен.

BEGIN;

INSERT INTO attendance_employee_profiles (faceid_employee_id, position)
VALUES
  ('1036440268', 'ofik'),
  ('1042277274', 'rayner'),
  ('1139962167', 'rayner'),
  ('1149901481', 'rayner'),
  ('1233941264', 'povar'),
  ('1250454269', 'Manager'),
  ('1251614771', 'xostes'),
  ('1451788590', 'rayner'),
  ('1528048758', 'rayner'),
  ('1656197164', 'moyka'),
  ('1802381922', 'rayner'),
  ('1854307188', 'Tezgox'),
  ('1930145800', 'xostes'),
  ('1934518185', 'ofik'),
  ('2025665971', 'xostes'),
  ('2118992177', 'ofik'),
  ('2138632114', 'rayner'),
  ('2315803772', 'Vallomat'),
  ('2340306162', 'rayner'),
  ('2540762862', 'moyka'),
  ('2654310049', 'povar'),
  ('2701257252', 'rayner'),
  ('2707392321', 'Manager'),
  ('2749630914', 'rayner'),
  ('2808677695', 'salat'),
  ('2902089666', 'povar'),
  ('2906339320', 'Kassa'),
  ('2919332167', 'Texnichka'),
  ('3031823980', 'rayner'),
  ('3139805403', 'povar'),
  ('3646813924', 'Konditer'),
  ('3716483407', 'BAR'),
  ('3929101078', 'rayner'),
  ('3939275546', 'Texnichka'),
  ('4054070840', 'Texnichka'),
  ('4129294475', 'xostes'),
  ('4300622134', 'Tezgox'),
  ('4554295470', 'rayner'),
  ('5014707953', 'ofik'),
  ('5040771371', 'povar'),
  ('5049842647', 'rayner'),
  ('5320408421', 'rayner'),
  ('5436995272', 'povar'),
  ('5525301497', 'ofik'),
  ('5548522361', 'povar'),
  ('5706765516', 'xostes'),
  ('5906849409', 'rayner'),
  ('5941651951', 'rayner'),
  ('6024470431', 'BAR'),
  ('6116217623', 'povar'),
  ('6145152805', 'povar'),
  ('6206182280', 'rayner'),
  ('6556890067', 'rayner'),
  ('6645369595', 'Texnichka'),
  ('6715493855', 'povar'),
  ('6737590266', 'rayner'),
  ('6942548262', 'rayner')
ON CONFLICT (faceid_employee_id) DO UPDATE
  SET position = EXCLUDED.position, updated_at = now()
  WHERE attendance_employee_profiles.position IS NULL
     OR btrim(attendance_employee_profiles.position) = '';

COMMIT;
