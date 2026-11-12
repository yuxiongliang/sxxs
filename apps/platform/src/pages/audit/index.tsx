import { SafetyCertificateOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import PageShell from '@/components/PageShell';
import type { PlatformAuditRecord } from '@/services/api';
import { listPlatformAudit } from '@/services/api';

function summarise(value: Record<string, unknown> | null): string {
  if (!value) return '—';
  return Object.entries(value)
    .map(([key, raw]) => key + '=' + JSON.stringify(raw))
    .join(' · ');
}

const columns: ColumnsType<PlatformAuditRecord> = [
  {
    title: '时间',
    dataIndex: 'created_at',
    width: 180,
    render: (value: string) => new Date(value).toLocaleString('zh-CN'),
  },
  {
    title: '操作',
    dataIndex: 'action',
    width: 220,
    render: (value: string) => <Tag color="geekblue">{value}</Tag>,
  },
  {
    title: '对象',
    width: 200,
    render: (_, record) => (
      <Typography.Text>
        {record.target_type || '—'}
        {record.target_id ? ' / ' + record.target_id : ''}
      </Typography.Text>
    ),
  },
  {
    title: '操作人 ID',
    dataIndex: 'actor_id',
    width: 110,
    render: (value: number | null) => value ?? '—',
  },
  {
    title: '变更后',
    render: (_, record) => (
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {summarise(record.after)}
      </Typography.Text>
    ),
  },
];

export default function PlatformAuditPage() {
  const audit = useQuery({
    queryKey: ['platform-audit'],
    queryFn: () => listPlatformAudit({ pageSize: 50 }),
  });

  return (
    <PageShell
      title="平台审计"
      subTitle="平台侧操作留痕：改全站配置会影响所有跟随系统的租户"
      icon={<SafetyCertificateOutlined />}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="这里只显示平台级操作"
        description="平台行以 tenant_id 为空标识，租户侧审计查不到；反过来租户侧的操作也不会出现在这里。"
      />
      <Card>
        <Table<PlatformAuditRecord>
          rowKey="id"
          size="small"
          loading={audit.isLoading}
          columns={columns}
          dataSource={audit.data?.list ?? []}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </PageShell>
  );
}
