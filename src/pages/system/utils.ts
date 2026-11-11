import dayjs from 'dayjs';

export const ROLE_OPTIONS = [
  { label: '管理员', value: 'admin', color: 'red' },
  { label: '运营人员', value: 'operator', color: 'blue' },
  { label: '只读用户', value: 'viewer', color: 'default' },
];

export const GENDER_OPTIONS = [
  { label: '男', value: 'male' },
  { label: '女', value: 'female' },
  { label: '其他', value: 'other' },
  { label: '保密', value: 'unknown' },
];

export const USER_STATUS_OPTIONS = [
  { label: '正常', value: 'active', color: 'success' },
  { label: '已停用', value: 'disabled', color: 'default' },
];

export const CHANNEL_OPTIONS = [
  { label: '短信', value: 'sms', color: 'orange' },
  { label: '邮件', value: 'email', color: 'blue' },
  { label: '站内信', value: 'inbox', color: 'purple' },
];

export const NOTIFICATION_STATUS_OPTIONS = [
  { label: '待发送', value: 'pending', color: 'gold' },
  { label: '发送中', value: 'sending', color: 'processing' },
  { label: '发送成功', value: 'success', color: 'success' },
  { label: '发送失败', value: 'failed', color: 'error' },
];

export const ATTACHMENT_CATEGORY_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '文档', value: 'document' },
  { label: '其他', value: 'other' },
];

export function optionLabel(
  options: { label: string; value: string }[],
  value?: string,
) {
  return options.find((item) => item.value === value)?.label ?? value ?? '-';
}

export function optionColor(
  options: { value: string; color?: string }[],
  value?: string,
) {
  return options.find((item) => item.value === value)?.color ?? 'default';
}

export function formatBytes(bytes: number) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatDateTime(value?: string) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-';
}

export function formatDate(value?: string) {
  return value ? dayjs(value).format('YYYY-MM-DD') : '-';
}
