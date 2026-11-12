export type UserRole = string;
export type UserStatus = 'active' | 'disabled';
export type Gender = 'male' | 'female' | 'other' | 'unknown';

export interface UserRecord {
  id: number;
  /** 对外用户编号：随机 20 位、全站唯一（与自增主键解耦） */
  public_id: string;
  username: string;
  nickname: string;
  email: string;
  phone?: string;
  role: UserRole;
  status: UserStatus;
  department?: string;
  department_id?: number;
  birthday?: string;
  gender?: Gender;
  last_login_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PageData<T> {
  list: T[];
  total: number;
  current: number;
  pageSize: number;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface SettingRecord {
  category: string;
  enabled: boolean;
  config: Record<string, unknown>;
  updated_at?: string;
  // ---- 配置继承（见后端 services/setting_resolver.py）----
  source?: 'inherit' | 'override' | 'forced_inherit';
  effective_source?: string;
  platform_active?: boolean;
  policy_locked?: boolean;
  inherit_allowed?: boolean;
  masked_fields?: string[];
  platform_updated_at?: string | null;
  tenant_config?: Record<string, unknown> | null;
}

export interface SettingTestResult {
  success: boolean;
  message: string;
  detail?: Record<string, unknown>;
  qr_code?: string;
}

export type AttachmentCategory = 'image' | 'video' | 'document' | 'other';

export interface AttachmentRecord {
  id: number;
  name: string;
  original_name: string;
  mime_type: string;
  size: number;
  extension: string;
  category: AttachmentCategory;
  storage: 'local' | 'oss' | 'remote' | string;
  url: string;
  uploader: string;
  uploader_role: string;
  source_module: string;
  // 可见范围与审核状态（审核结论由平台给出，租户只读）
  visibility: string;
  review_status: string;
  reject_reason?: string | null;
  admin_hidden: boolean;
  deleted_at?: string | null;
  checksum: string;
  created_at: string;
}

export interface DepartmentRecord {
  id: number;
  name: string;
  code?: string;
  description?: string;
  status: 'active' | 'disabled';
  sort: number;
  created_at: string;
  updated_at: string;
}

export interface PermissionItem {
  code: string;
  name: string;
  module: string;
  action: string;
}

export interface RolePermissions {
  all: PermissionItem[];
  selected: string[];
}

export interface RoleRecord {
  id: number;
  code: string;
  name: string;
  description?: string;
  status: 'active' | 'disabled';
  sort: number;
  created_at: string;
  updated_at: string;
}

export interface AttachmentStats {
  total: number;
  images: number;
  videos: number;
  documents: number;
  others: number;
  totalSize: number;
}

export type NotificationChannel = 'sms' | 'email' | 'inbox';
export type NotificationStatus = 'pending' | 'sending' | 'success' | 'failed';

export interface NotificationRecord {
  id: number;
  title: string;
  channel: NotificationChannel;
  template: string;
  audience: string;
  content: string;
  status: NotificationStatus;
  scheduled_at?: string;
  sent_at?: string;
  total: number;
  success_count: number;
  failed_count: number;
  error_message?: string;
  created_at: string;
}

export interface NotificationStats {
  total: number;
  success: number;
  failed: number;
  pending: number;
  channels: Record<string, number>;
}
