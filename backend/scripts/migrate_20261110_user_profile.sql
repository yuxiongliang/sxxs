-- 2026-11-10: user profile fields + departments/roles dictionaries
-- Run against the project database (PostgreSQL 18.6 on port 5433).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    code VARCHAR(64) UNIQUE,
    description VARCHAR(255),
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    sort INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(255),
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    sort INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS birthday DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(16);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS department_id INTEGER;

CREATE INDEX IF NOT EXISTS ix_users_department_id ON users (department_id);
CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);

INSERT INTO departments (name, status, sort)
SELECT DISTINCT department, 'active', 0
FROM users
WHERE department IS NOT NULL AND department <> ''
ON CONFLICT (name) DO NOTHING;

UPDATE users u
SET department_id = d.id
FROM departments d
WHERE u.department = d.name AND u.department_id IS NULL;

INSERT INTO roles (code, name, description, status, sort)
VALUES
    ('admin', '管理员', '拥有系统全部权限', 'active', 10),
    ('operator', '运营人员', '负责日常运营与内容维护', 'active', 20),
    ('viewer', '只读用户', '只读查看数据', 'active', 30)
ON CONFLICT (code) DO NOTHING;

INSERT INTO roles (code, name, description, status, sort)
SELECT DISTINCT role, role, '迁移角色', 'active', 100
FROM users
WHERE role IS NOT NULL AND role <> ''
ON CONFLICT (code) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_department_id'
    ) THEN
        ALTER TABLE users
        ADD CONSTRAINT fk_users_department_id
        FOREIGN KEY (department_id) REFERENCES departments(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_role_code'
    ) THEN
        ALTER TABLE users
        ADD CONSTRAINT fk_users_role_code
        FOREIGN KEY (role) REFERENCES roles(code);
    END IF;
END $$;
