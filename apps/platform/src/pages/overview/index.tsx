import { DashboardOutlined, GlobalOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { TenantDomainRecord, TenantOverviewRecord } from '@/services/api';
import {
  createTenantDomain,
  deleteTenantDomain,
  listTenantDomains,
  listTenantOverview,
  verifyTenantDomain,
} from '@/services/api';

const DOMAIN_STATUS: Record<
  TenantDomainRecord['status'],
  { color: string; text: string }
> = {
  active: { color: 'green', text: '已生效' },
  pending: { color: 'orange', text: '待验证' },
  failed: { color: 'red', text: '验证失败' },
  disabled: { color: 'default', text: '已停用' },
};

const DOMAIN_KIND: Record<TenantDomainRecord['kind'], string> = {
  subdomain: '自有子域',
  custom: '客户域名',
};

function DomainCell({ record }: { record: TenantOverviewRecord }) {
  const { primary_host: primaryHost, active, pending, total } = record.domain;
  return (
    <Space orientation="vertical" size={0}>
      {primaryHost ? (
        <Typography.Text>{primaryHost}</Typography.Text>
      ) : (
        <Typography.Text type="secondary">未绑定域名</Typography.Text>
      )}
      <Space size={4}>
        {active > 0 ? <Tag color="green">生效 {active}</Tag> : null}
        {pending > 0 ? <Tag color="orange">待验证 {pending}</Tag> : null}
        {total === 0 ? <Tag>无</Tag> : null}
      </Space>
    </Space>
  );
}

function buildColumns(
  onManageDomains: (record: TenantOverviewRecord) => void,
): ColumnsType<TenantOverviewRecord> {
  return [
    {
      title: '租户',
      width: 240,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
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
        <Space orientation="vertical" size={0}>
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
      width: 160,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
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
      width: 220,
      render: (_, record) => <DomainCell record={record} />,
    },
    {
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Button
          type="link"
          icon={<GlobalOutlined />}
          onClick={() => onManageDomains(record)}
        >
          域名
        </Button>
      ),
    },
  ];
}

interface TenantDomainDrawerProps {
  tenant: TenantOverviewRecord | null;
  onClose: () => void;
}

function TenantDomainDrawer({ tenant, onClose }: TenantDomainDrawerProps) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<{ host: string; kind: 'custom' | 'subdomain' }>();
  const tenantId = tenant?.tenant_id ?? 0;

  const domains = useQuery({
    queryKey: ['tenant-domains', tenantId],
    queryFn: () => listTenantDomains(tenantId),
    enabled: Boolean(tenant),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['tenant-domains', tenantId] });
    // 概览页的域名计数也要跟着变，否则关掉抽屉还显示旧状态
    queryClient.invalidateQueries({ queryKey: ['tenant-overview'] });
  };

  const create = useMutation({
    mutationFn: (values: { host: string; kind: 'custom' | 'subdomain' }) =>
      createTenantDomain(tenantId, values),
    onSuccess: (record) => {
      message.success(
        record.status === 'active'
          ? '域名已绑定并生效'
          : '域名已绑定，等 TXT 记录生效后点验证',
      );
      form.resetFields();
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const verify = useMutation({
    mutationFn: (domainId: number) => verifyTenantDomain(tenantId, domainId),
    onSuccess: (record) => {
      if (record.status === 'active') {
        message.success('验证通过，域名已生效');
      } else {
        message.warning('还没查到 TXT 记录，DNS 生效后再试一次');
      }
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (domainId: number) => deleteTenantDomain(tenantId, domainId),
    onSuccess: () => {
      message.success('域名已解绑');
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const pending = (domains.data ?? []).find(
    (item) => item.status === 'pending' && item.dns_record,
  );

  const columns: ColumnsType<TenantDomainRecord> = [
    {
      title: '域名',
      dataIndex: 'host',
      render: (value: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{value}</Typography.Text>
          <Tag color={record.kind === 'subdomain' ? 'blue' : 'purple'}>
            {DOMAIN_KIND[record.kind]}
          </Tag>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: TenantDomainRecord['status']) => (
        <Tag color={DOMAIN_STATUS[value].color}>
          {DOMAIN_STATUS[value].text}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size={0}>
          {record.status === 'active' ? null : (
            <Button
              type="link"
              loading={verify.isPending && verify.variables === record.id}
              onClick={() => verify.mutate(record.id)}
            >
              验证
            </Button>
          )}
          <Popconfirm
            title="解绑后该域名立即无法访问，确认？"
            onConfirm={() => remove.mutate(record.id)}
          >
            <Button type="link" danger>
              解绑
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Drawer
      title={tenant ? `${tenant.name} · 域名` : '域名'}
      size={720}
      open={Boolean(tenant)}
      onClose={() => {
        form.resetFields();
        onClose();
      }}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="自定义域名要先证明所有权"
        description="在域名服务商处添加下面这条 TXT 记录，DNS 生效后点「验证」；自有子域不需要验证。"
      />

      {pending?.dns_record ? (
        <Card
          size="small"
          style={{ marginBottom: 16 }}
          title={`待验证：${pending.host}`}
        >
          <Space orientation="vertical" size={4}>
            <Typography.Text type="secondary">记录类型：TXT</Typography.Text>
            <Typography.Text copyable>
              {pending.dns_record.name}
            </Typography.Text>
            <Typography.Text copyable>
              {pending.dns_record.value}
            </Typography.Text>
          </Space>
        </Card>
      ) : null}

      <Form
        form={form}
        layout="inline"
        initialValues={{ kind: 'custom' }}
        onFinish={(values) => create.mutate(values)}
        style={{ marginBottom: 16 }}
      >
        <Form.Item
          name="host"
          rules={[{ required: true, message: '填域名，例如 shop.example.com' }]}
        >
          <Input placeholder="shop.example.com" style={{ width: 260 }} />
        </Form.Item>
        <Form.Item name="kind">
          <Select
            style={{ width: 130 }}
            options={[
              { value: 'custom', label: '客户域名' },
              { value: 'subdomain', label: '自有子域' },
            ]}
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={create.isPending}>
            绑定
          </Button>
        </Form.Item>
      </Form>

      <Table<TenantDomainRecord>
        rowKey="id"
        size="small"
        loading={domains.isLoading}
        columns={columns}
        dataSource={domains.data ?? []}
        pagination={false}
      />
    </Drawer>
  );
}

export default function TenantOverviewPage() {
  const [managed, setManaged] = useState<TenantOverviewRecord | null>(null);
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
          columns={buildColumns(setManaged)}
          dataSource={overview.data ?? []}
          pagination={false}
        />
      </Card>
      <TenantDomainDrawer tenant={managed} onClose={() => setManaged(null)} />
    </PageShell>
  );
}
