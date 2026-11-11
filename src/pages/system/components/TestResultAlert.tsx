import { Alert } from 'antd';
import type { SettingTestResult } from '@/services/system/types';

export default function TestResultAlert({
  result,
}: {
  result?: SettingTestResult;
}) {
  if (!result) return null;
  return (
    <Alert
      showIcon
      closable
      type={result.success ? 'success' : 'error'}
      title={result.success ? '连接测试通过' : '连接测试失败'}
      description={result.message}
      style={{ marginBottom: 16 }}
    />
  );
}
