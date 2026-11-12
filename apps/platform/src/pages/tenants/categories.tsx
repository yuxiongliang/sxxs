import { AppstoreOutlined, ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { PlatformCategoryRecord } from '@/services/api';
import { listPlatformCategories, listTenants } from '@/services/api';

export default function ServiceCategoriesPage() {
  const [tenantId, setTenantId] = useState<number | undefined>();
  const [keyword, setKeyword] = useState('');

  const tenants = useQuery({
    queryKey: ['platform-tenants'],
    queryFn: listTenants,
  });
  const categories = useQuery({
    queryKey: ['platform-categories', tenantId ?? 'all', keyword],
    queryFn: () =>
      listPlatformCategories({ tenantId, q: keyword || undefined }),
  });

  const columns: ColumnsType<PlatformCategoryRecord> = [
    {
      title: '租户',
      width: 220,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>{record.tenant_name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.tenant_slug}
          </Typography.Text>
        </Space>
      ),
    },
    { title: '类目名称', dataIndex: 'name', width: 200 },
    {
      title: '标识（slug）',
      dataIndex: 'slug',
      width: 180,
      render: (value: string) => (
        <Typography.Text code>{value}</Typography.Text>
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
    { title: '排序', dataIndex: 'sort', width: 80 },
    {
      title: '商品数',
      dataIndex: 'product_count',
      width: 100,
      render: (value: number) =>
        value > 0 ? (
          <Tag color="blue">{value}</Tag>
        ) : (
          <Typography.Text type="secondary">0</Typography.Text>
        ),
    },
  ];

  return (
    <PageShell
      title="服务类目"
      subTitle="各租户已开通的经营类目与商品数（只读总览）"
      icon={<AppstoreOutlined />}
      extra={
        <Button icon={<ReloadOutlined />} onClick={() => categories.refetch()}>
          刷新
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="这里只做只读总览"
        description="类目目前由各租户自己维护，平台侧只汇总查看。若要由平台统一维护「类目字典」供租户选用，需要先定义审批与迁移规则，属于另一批需求。"
      />

      <Card title="筛选" size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            allowClear
            placeholder="全部租户"
            style={{ width: 240 }}
            loading={tenants.isLoading}
            value={tenantId}
            onChange={(value) => setTenantId(value)}
            options={(tenants.data ?? []).map((item) => ({
              value: item.id,
              label: `${item.name}（${item.slug}）`,
            }))}
          />
          <Input.Search
            allowClear
            placeholder="按类目名或 slug 搜索"
            style={{ width: 260 }}
            onSearch={(value) => setKeyword(value.trim())}
          />
        </Space>
      </Card>

      <Card>
        <Table<PlatformCategoryRecord>
          rowKey="id"
          size="small"
          loading={categories.isLoading}
          columns={columns}
          dataSource={categories.data ?? []}
          pagination={{ pageSize: 20, hideOnSinglePage: true }}
        />
      </Card>
    </PageShell>
  );
}
