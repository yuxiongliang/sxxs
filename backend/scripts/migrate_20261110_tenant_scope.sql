-- 2026-11-10: add tenant_id to existing business tables
ALTER TABLE departments ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS tenant_id INTEGER;

UPDATE departments SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE system_settings SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE attachments SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE notifications SET tenant_id = 1 WHERE tenant_id IS NULL;

ALTER TABLE departments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE system_settings ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE attachments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE notifications ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE departments DROP CONSTRAINT IF EXISTS departments_name_key;
ALTER TABLE departments DROP CONSTRAINT IF EXISTS departments_code_key;
ALTER TABLE system_settings DROP CONSTRAINT IF EXISTS system_settings_category_key;

ALTER TABLE departments ADD CONSTRAINT uq_department_tenant_name UNIQUE (tenant_id, name);
ALTER TABLE system_settings ADD CONSTRAINT uq_setting_tenant_category UNIQUE (tenant_id, category);

CREATE INDEX IF NOT EXISTS ix_departments_tenant_id ON departments (tenant_id);
CREATE INDEX IF NOT EXISTS ix_system_settings_tenant_id ON system_settings (tenant_id);
CREATE INDEX IF NOT EXISTS ix_attachments_tenant_id ON attachments (tenant_id);
CREATE INDEX IF NOT EXISTS ix_notifications_tenant_id ON notifications (tenant_id);