-- MADO CHECKLIST — Initial schema (v1.0)
-- PostgreSQL 15+

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =========================================================
-- branches
-- =========================================================
CREATE TABLE branches (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    address     VARCHAR(255),
    city        VARCHAR(100),
    timezone    VARCHAR(50) NOT NULL DEFAULT 'Asia/Tashkent',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- roles
-- =========================================================
CREATE TABLE roles (
    id                SERIAL PRIMARY KEY,
    code              VARCHAR(50) UNIQUE NOT NULL,
    name_ru           VARCHAR(100) NOT NULL,
    name_uz           VARCHAR(100),
    name_en           VARCHAR(100),
    name_tr           VARCHAR(100),
    category          VARCHAR(20) NOT NULL CHECK (category IN ('staff', 'management')),
    permission_level  SMALLINT NOT NULL DEFAULT 0
);

-- =========================================================
-- employees
-- =========================================================
CREATE TABLE employees (
    id                  BIGSERIAL PRIMARY KEY,
    full_name           VARCHAR(150) NOT NULL,
    telegram_id         BIGINT UNIQUE,
    phone               VARCHAR(30),
    role_id             INT NOT NULL REFERENCES roles(id),
    preferred_language  VARCHAR(5) NOT NULL DEFAULT 'ru' CHECK (preferred_language IN ('ru','uz','en','tr')),
    status              VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','fired')),
    hired_at            DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_employees_role ON employees(role_id);
CREATE INDEX idx_employees_status ON employees(status);

-- =========================================================
-- users (web accounts for management roles)
-- =========================================================
CREATE TABLE users (
    id               BIGSERIAL PRIMARY KEY,
    employee_id      BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    email            VARCHAR(150) UNIQUE NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    is_2fa_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- employee_branches (many-to-many)
-- =========================================================
CREATE TABLE employee_branches (
    id            BIGSERIAL PRIMARY KEY,
    employee_id   BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    branch_id     BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (employee_id, branch_id)
);

CREATE INDEX idx_employee_branches_branch ON employee_branches(branch_id);

-- =========================================================
-- shifts
-- =========================================================
CREATE TABLE shifts (
    id            BIGSERIAL PRIMARY KEY,
    employee_id   BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    branch_id     BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    shift_date    DATE NOT NULL,
    starts_at     TIME NOT NULL,
    ends_at       TIME NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','completed','no_show'))
);

CREATE INDEX idx_shifts_employee_date ON shifts(employee_id, shift_date);
CREATE INDEX idx_shifts_branch_date ON shifts(branch_id, shift_date);

-- =========================================================
-- checklist_templates
-- =========================================================
CREATE TABLE checklist_templates (
    id           BIGSERIAL PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    role_id      INT NOT NULL REFERENCES roles(id),
    stage        VARCHAR(20) NOT NULL CHECK (stage IN ('opening','during_shift','closing')),
    branch_id    BIGINT REFERENCES branches(id),  -- NULL = общий для всех филиалов
    starts_at    TIME NOT NULL,
    deadline_at  TIME NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_by   BIGINT REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_templates_role_stage ON checklist_templates(role_id, stage);
CREATE INDEX idx_templates_branch ON checklist_templates(branch_id);

-- =========================================================
-- checklist_sections
-- =========================================================
CREATE TABLE checklist_sections (
    id           BIGSERIAL PRIMARY KEY,
    template_id  BIGINT NOT NULL REFERENCES checklist_templates(id) ON DELETE CASCADE,
    name         VARCHAR(150) NOT NULL,
    sort_order   INT NOT NULL DEFAULT 0
);

-- =========================================================
-- checklist_tasks
-- =========================================================
CREATE TABLE checklist_tasks (
    id                            BIGSERIAL PRIMARY KEY,
    template_id                   BIGINT NOT NULL REFERENCES checklist_templates(id) ON DELETE CASCADE,
    section_id                    BIGINT REFERENCES checklist_sections(id) ON DELETE SET NULL,
    title_ru                      VARCHAR(255) NOT NULL,
    title_uz                      VARCHAR(255),
    title_en                      VARCHAR(255),
    title_tr                      VARCHAR(255),
    task_type                     VARCHAR(20) NOT NULL CHECK (task_type IN
                                   ('checkbox','number','temperature','text','photo','photo_geo','yes_no')),
    is_required                   BOOLEAN NOT NULL DEFAULT TRUE,
    requires_photo                BOOLEAN NOT NULL DEFAULT FALSE,
    requires_comment_on_negative  BOOLEAN NOT NULL DEFAULT FALSE,
    standard_code                 VARCHAR(30),
    sort_order                    INT NOT NULL DEFAULT 0,
    due_offset_minutes            INT
);

CREATE INDEX idx_tasks_template ON checklist_tasks(template_id);

-- =========================================================
-- checklist_assignments
-- =========================================================
CREATE TABLE checklist_assignments (
    id               BIGSERIAL PRIMARY KEY,
    template_id      BIGINT NOT NULL REFERENCES checklist_templates(id),
    employee_id      BIGINT NOT NULL REFERENCES employees(id),
    branch_id        BIGINT NOT NULL REFERENCES branches(id),
    shift_id         BIGINT REFERENCES shifts(id),
    assignment_date  DATE NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'not_started'
                     CHECK (status IN ('not_started','in_progress','completed','overdue')),
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    UNIQUE (template_id, employee_id, assignment_date)
);

CREATE INDEX idx_assignments_employee_date ON checklist_assignments(employee_id, assignment_date);
CREATE INDEX idx_assignments_branch_date ON checklist_assignments(branch_id, assignment_date);
CREATE INDEX idx_assignments_status ON checklist_assignments(status);

-- =========================================================
-- task_results
-- =========================================================
CREATE TABLE task_results (
    id             BIGSERIAL PRIMARY KEY,
    assignment_id  BIGINT NOT NULL REFERENCES checklist_assignments(id) ON DELETE CASCADE,
    task_id        BIGINT NOT NULL REFERENCES checklist_tasks(id),
    value          JSONB,
    status         VARCHAR(20) NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('done','problem','not_relevant','pending')),
    completed_at   TIMESTAMPTZ,
    is_overdue     BOOLEAN NOT NULL DEFAULT FALSE,
    completed_by   BIGINT REFERENCES employees(id),
    UNIQUE (assignment_id, task_id)
);

CREATE INDEX idx_task_results_assignment ON task_results(assignment_id);
CREATE INDEX idx_task_results_status ON task_results(status);

-- =========================================================
-- photos
-- =========================================================
CREATE TABLE photos (
    id              BIGSERIAL PRIMARY KEY,
    task_result_id  BIGINT NOT NULL REFERENCES task_results(id) ON DELETE CASCADE,
    file_url        VARCHAR(500) NOT NULL,
    latitude        NUMERIC(9,6),
    longitude       NUMERIC(9,6),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_photos_task_result ON photos(task_result_id);

-- =========================================================
-- issues
-- =========================================================
CREATE TABLE issues (
    id               BIGSERIAL PRIMARY KEY,
    task_result_id   BIGINT REFERENCES task_results(id) ON DELETE SET NULL,
    branch_id        BIGINT NOT NULL REFERENCES branches(id),
    reported_by      BIGINT NOT NULL REFERENCES employees(id),
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    assigned_to      BIGINT REFERENCES employees(id),
    due_at           TIMESTAMPTZ,
    status           VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (status IN ('new','in_progress','resolved')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_issues_branch_status ON issues(branch_id, status);
CREATE INDEX idx_issues_assigned_to ON issues(assigned_to);

-- =========================================================
-- issue_comments
-- =========================================================
CREATE TABLE issue_comments (
    id          BIGSERIAL PRIMARY KEY,
    issue_id    BIGINT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author_id   BIGINT NOT NULL REFERENCES employees(id),
    comment     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_issue_comments_issue ON issue_comments(issue_id);

-- =========================================================
-- notifications
-- =========================================================
CREATE TABLE notifications (
    id            BIGSERIAL PRIMARY KEY,
    recipient_id  BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    type          VARCHAR(30) NOT NULL CHECK (type IN ('reminder','overdue','escalation','issue_assigned')),
    payload       JSONB,
    is_read       BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_recipient_read ON notifications(recipient_id, is_read);

-- =========================================================
-- audit_logs
-- =========================================================
CREATE TABLE audit_logs (
    id           BIGSERIAL PRIMARY KEY,
    actor_id     BIGINT REFERENCES employees(id),
    action       VARCHAR(100) NOT NULL,
    entity_type  VARCHAR(50) NOT NULL,
    entity_id    BIGINT,
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_id);

COMMIT;
