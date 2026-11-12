import { DashboardOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import PageShell from '@/components/PageShell';
import type { TenantOverviewRecord } from '@/services/api';
import { listTenantOverview } from '@/services/api';

const columns: ColumnsType<TenantOverviewRecord> = [
  {
    title: '租户',
    width: 240,
    render: (_, record) => (
      <Space direction="vertical" size={0}>
        <Typography.Text strong>{record.name}</Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {record.slug} · #{record.tenant_id}
        </Typography.Text>
      </Space>
    ),
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 100,
    render: (value: string) => (
      <Tag color={value === 'active' ? 'green' : 'default'}>{value}</Tag>
    ),
  },
  {
    title: '品牌',
    width: 200,
    render: (_, record) => (
      <Space direction="vertical" size={0}>
        <Typography.Text>{record.brand.display_name}</Typography.Text>
        <Space size={4}>
          {record.brand.customized ? (
            <Tag color="blue">已自定义</Tag>
          ) : (
            <Tag>默认</Tag>
          )}
          {record.brand.has_logo ? <Tag color="purple">有 logo</Tag> : null}
        </Space>
      </Space>
    ),
  },
  {
    title: '支付',
    width: 180,
    render: (_, record) => (
      <Space direction="vertical" size={0}>
        {record.payment.configured ? (
          <Tag color="green">已配置</Tag>
        ) : (
          <Tag color="red">未配置</Tag>
        )}
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          source: {record.payment.source}
        </Typography.Text>
      </Space>
    ),
  },
  {
    title: '自定义域名',
    width: 200,
    render: (_, record) =>
      record.domain.supported ? (
        <Tag color="green">已支持</Tag>
      ) : (
        <Typography.Text type="secondary">{record.domain.note}</Typography.Text>
      ),
  },
];

export default function TenantOverviewPage() {
  const overview = useQuery({
    queryKey: ['tenant-overview'],
    queryFn: listTenantOverview,
  });

  return (
    <PageShell
      title="租户概览"
      subTitle="排障入口：每个租户的品牌、支付与域名状态"
      icon={<DashboardOutlined />}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="「未配置」是按占位值判定的"
        description="租户照抄默认 alipay / wechat appId 时会被判为未配置——这类租户实际收不了款，需要催办。"
      />
      <Card>
        <Table<TenantOverviewRecord>
          rowKey="tenant_id"
          size="small"
          loading={overview.isLoading}
          columns={columns}
          dataSource={overview.data ?? []}
          pagination={false}
        />
      </Card>
    </PageShell>
  );
}
