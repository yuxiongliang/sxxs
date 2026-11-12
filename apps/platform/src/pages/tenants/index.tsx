import {
  ClusterOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';
import PageShell from '@/components/PageShell';
import type { TenantOverviewRecord, TenantWithPlan } from '@/services/api';
import {
  createTenant,
  listPlans,
  listTenantOverview,
  listTenantsWithPlan,
  renewTenant,
  resumeTenant,
  subscribeTenant,
  suspendTenant,
  updateTenant,
} from '@/services/api';
import TenantDomainDrawer from './DomainDrawer';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const statusColor = (status?: string) =>
  status === 'active'
    ? 'success'
    : status === 'trialing'
      ? 'blue'
      : status === 'suspended' || status === 'past_due'
        ? 'red'
        : 'default';

function BrandCell({ overview }: { overview?: TenantOverviewRecord }) {
  if (!overview) return <Typography.Text type="secondary">—</Typography.Text>;
  return (
    <Space orientation="vertical" size={0}>
      <Typography.Text>{overview.brand.display_name}</Typography.Text>
      <Space size={4}>
        {overview.brand.customized ? (
          <Tag color="blue">已自定义</Tag>
        ) : (
          <Tag>默认</Tag>
        )}
        {overview.brand.has_logo ? <Tag color="purple">有 logo</Tag> : null}
      </Space>
    </Space>
  );
}

function PaymentCell({ overview }: { overview?: TenantOverviewRecord }) {
  if (!overview) return <Typography.Text type="secondary">—</Typography.Text>;
  return (
    <Space orientation="vertical" size={0}>
      {overview.payment.configured ? (
        <Tag color="green">已配置</Tag>
      ) : (
        <Tag color="red">未配置</Tag>
      )}
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        source: {overview.payment.source}
      </Typography.Text>
    </Space>
  );
}

function DomainCell({ overview }: { overview?: TenantOverviewRecord }) {
  if (!overview) return <Typography.Text type="secondary">—</Typography.Text>;
  const { primary_host: primaryHost, active, pending, total } = overview.domain;
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

const PlatformTenantsPage: React.FC = () => {
  const { message } = App.useApp();
  const [createOpen, setCreateOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<TenantWithPlan>();
  const [domainTarget, setDomainTarget] = useState<TenantWithPlan | null>(null);
  const [createForm] = Form.useForm();
  const [renameForm] = Form.useForm();

  const tenants = useQuery({
    queryKey: ['platform-tenants-plan'],
    queryFn: listTenantsWithPlan,
  });
  const plans = useQuery({ queryKey: ['platform-plans'], queryFn: listPlans });
  // 概览数据（品牌 / 支付 / 域名）不单独开页面，直接并进这张表
  const overview = useQuery({
    queryKey: ['tenant-overview'],
    queryFn: listTenantOverview,
  });

  const overviewByTenant = useMemo(() => {
    const map = new Map<number, TenantOverviewRecord>();
    for (const row of overview.data ?? []) map.set(row.tenant_id, row);
    return map;
  }, [overview.data]);

  const refreshAll = async () => {
    await Promise.all([tenants.refetch(), plans.refetch(), overview.refetch()]);
  };

  const handleCreate = async () => {
    const values = await createForm.validateFields();
    await createTenant(values);
    message.success('租户创建成功（已开通免费版试用）');
    setCreateOpen(false);
    createForm.resetFields();
    await refreshAll();
  };

  const handleRename = async () => {
    if (!renameTarget) return;
    const values = await renameForm.validateFields();
    await updateTenant(renameTarget.id, { name: values.name });
    message.success('租户已更新');
    setRenameTarget(undefined);
    await refreshAll();
  };

  const tenantColumns: ColumnsType<TenantWithPlan> = [
    {
      title: '租户',
      dataIndex: 'name',
      width: 200,
      render: (value: string, record) => (
        <Space orientation="vertical" size={0}>
          <Space>
            <ClusterOutlined style={{ color: '#1677ff' }} />
            <strong>{value}</strong>
          </Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.slug} · #{record.id}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag>,
    },
    {
      title: '套餐',
      key: 'plan',
      width: 190,
      render: (_, record) => (
        <Space orientation="vertical" size={2}>
          <Select
            size="small"
            style={{ width: 150 }}
            value={record.plan?.id}
            placeholder="未订阅"
            options={(plans.data ?? []).map((plan) => ({
              value: plan.id,
              label: `${plan.name}（${yuan(plan.price_cents)}/${plan.period}）`,
            }))}
            onChange={async (planId) => {
              await subscribeTenant(record.id, planId as number);
              message.success('套餐已变更');
              await refreshAll();
            }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.subscription
              ? `${record.subscription.status} · 剩 ${record.days_left ?? 0} 天`
              : '无订阅记录'}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '用量 / 配额',
      key: 'usage',
      width: 170,
      render: (_, record) => {
        const used = record.used?.products ?? 0;
        const limit = record.quotas?.products;
        if (limit === null || limit === undefined) {
          return <Tag color="green">商品不限（已用 {used}）</Tag>;
        }
        const percent =
          limit === 0 ? 100 : Math.min(100, Math.round((used / limit) * 100));
        return (
          <Progress
            percent={percent}
            size="small"
            status={
              record.exceeded?.includes('products') ? 'exception' : 'normal'
            }
            format={() => `${used}/${limit}`}
          />
        );
      },
    },
    {
      title: '品牌',
      key: 'brand',
      width: 150,
      render: (_, record) => (
        <BrandCell overview={overviewByTenant.get(record.id)} />
      ),
    },
    {
      title: '支付',
      key: 'payment',
      width: 130,
      render: (_, record) => (
        <PaymentCell overview={overviewByTenant.get(record.id)} />
      ),
    },
    {
      title: '域名',
      key: 'domain',
      width: 190,
      render: (_, record) => (
        <DomainCell overview={overviewByTenant.get(record.id)} />
      ),
    },
    {
      title: '操作',
      width: 250,
      render: (_, record) => (
        <Space size={2} wrap>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setRenameTarget(record);
              renameForm.setFieldsValue({ name: record.name });
            }}
          >
            改名
          </Button>
          <Button
            type="link"
            size="small"
            onClick={async () => {
              const result = await renewTenant(record.id, 30);
              message.success(
                result.invoice
                  ? `续费成功，账单 ${result.invoice.invoice_no}`
                  : '续费成功',
              );
              await refreshAll();
            }}
          >
            续费
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => setDomainTarget(record)}
          >
            域名
          </Button>
          {record.status === 'active' ? (
            <Popconfirm
              title="停用后该租户所有 API 将返回 403，确认？"
              onConfirm={async () => {
                try {
                  await suspendTenant(record.id, '控制台停用');
                  message.success('租户已停用');
                  await refreshAll();
                } catch (error: any) {
                  message.error(error?.message || '停用失败');
                }
              }}
            >
              <Button
                type="link"
                size="small"
                danger
                disabled={record.slug === 'demo'}
              >
                停用
              </Button>
            </Popconfirm>
          ) : (
            <Button
              type="link"
              size="small"
              onClick={async () => {
                await resumeTenant(record.id);
                message.success('租户已恢复');
                await refreshAll();
              }}
            >
              恢复
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="租户"
      subTitle="租户概况一屏看完：套餐、用量、品牌、支付与域名"
      icon={<ClusterOutlined />}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refreshAll()}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            开通租户
          </Button>
        </Space>
      }
    >
      <Card>
        <Table
          rowKey="id"
          loading={tenants.isLoading || overview.isLoading}
          columns={tenantColumns}
          dataSource={tenants.data ?? []}
          scroll={{ x: 1580 }}
          pagination={false}
        />
      </Card>

      <Modal
        title="开通租户"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        okText="开通"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item label="租户名称" name="name" rules={[{ required: true }]}>
            <Input placeholder="Acme Marketplace" />
          </Form.Item>
          <Form.Item
            label="Slug"
            name="slug"
            rules={[
              {
                required: true,
                pattern: /^[a-z0-9-]+$/,
                message: '仅小写字母/数字/中划线',
              },
            ]}
          >
            <Input placeholder="acme" />
          </Form.Item>
          <Form.Item
            label="管理员邮箱"
            name="email"
            rules={[{ required: true }]}
          >
            <Input placeholder="owner@example.com" />
          </Form.Item>
          <Form.Item
            label="管理员昵称"
            name="nickname"
            rules={[{ required: true }]}
          >
            <Input placeholder="站长" />
          </Form.Item>
          <Form.Item
            label="初始密码"
            name="password"
            rules={[{ required: true, min: 6 }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="租户改名"
        open={Boolean(renameTarget)}
        onCancel={() => setRenameTarget(undefined)}
        onOk={handleRename}
        okText="保存"
      >
        <Form form={renameForm} layout="vertical">
          <Form.Item label="名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <TenantDomainDrawer
        tenantId={domainTarget ? domainTarget.id : null}
        tenantName={domainTarget?.name}
        onClose={() => setDomainTarget(null)}
      />
    </PageShell>
  );
};

export default PlatformTenantsPage;
