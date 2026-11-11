import {
  ClusterOutlined,
  PlusOutlined,
  ReloadOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import React, { useState } from 'react';
import type {
  InvoiceRecord,
  PlanRecord,
  TenantWithPlan,
} from '@/services/platform/api';
import {
  createPlan,
  createTenant,
  listInvoices,
  listPlans,
  listTenantsWithPlan,
  payInvoice,
  renewTenant,
  resumeTenant,
  subscribeTenant,
  suspendTenant,
  updateTenant,
} from '@/services/platform/api';
import SettingPage from '../../system/components/SettingPage';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const statusColor = (status?: string) =>
  status === 'active'
    ? 'success'
    : status === 'trialing'
      ? 'blue'
      : status === 'suspended' || status === 'past_due'
        ? 'red'
        : 'default';

const PlatformTenantsPage: React.FC = () => {
  const { message } = App.useApp();
  const [createOpen, setCreateOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<TenantWithPlan>();
  const [createForm] = Form.useForm();
  const [planForm] = Form.useForm();
  const [renameForm] = Form.useForm();

  const tenants = useQuery({
    queryKey: ['platform-tenants-plan'],
    queryFn: listTenantsWithPlan,
  });
  const plans = useQuery({ queryKey: ['platform-plans'], queryFn: listPlans });
  const invoices = useQuery({
    queryKey: ['platform-invoices'],
    queryFn: () => listInvoices(),
  });

  const refreshAll = async () => {
    await Promise.all([tenants.refetch(), plans.refetch(), invoices.refetch()]);
  };

  const handleCreate = async () => {
    const values = await createForm.validateFields();
    await createTenant(values);
    message.success('租户创建成功（已开通免费版试用）');
    setCreateOpen(false);
    createForm.resetFields();
    await refreshAll();
  };

  const handleCreatePlan = async () => {
    const values = await planForm.validateFields();
    try {
      await createPlan({
        code: values.code,
        name: values.name,
        price_cents: Math.round((values.price_yuan ?? 0) * 100),
        period: values.period,
        trial_days: values.trial_days ?? 14,
        quotas: {
          products: values.products === undefined ? null : values.products,
          members: values.members === undefined ? null : values.members,
        },
        features: values.features ?? [],
      });
      message.success('套餐已创建');
      setPlanOpen(false);
      planForm.resetFields();
      await plans.refetch();
    } catch (error: any) {
      message.error(error?.message || '创建套餐失败');
    }
  };

  const handleRename = async () => {
    if (!renameTarget) return;
    const values = await renameForm.validateFields();
    await updateTenant(renameTarget.id, { name: values.name });
    message.success('租户已更新');
    setRenameTarget(undefined);
    await tenants.refetch();
  };

  const tenantColumns: ColumnsType<TenantWithPlan> = [
    {
      title: '租户',
      dataIndex: 'name',
      render: (value: string, record) => (
        <Space orientation="vertical" size={0}>
          <Space>
            <ClusterOutlined style={{ color: '#1677ff' }} />
            <strong>{value}</strong>
          </Space>
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>{record.slug}</span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
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
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>
            {record.subscription
              ? `${record.subscription.status} · 剩 ${record.days_left ?? 0} 天`
              : '无订阅记录'}
          </span>
        </Space>
      ),
    },
    {
      title: '用量 / 配额',
      key: 'usage',
      width: 190,
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
      title: '操作',
      width: 290,
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

  const planColumns: ColumnsType<PlanRecord> = [
    { title: '编码', dataIndex: 'code', width: 130 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '价格',
      dataIndex: 'price_cents',
      width: 150,
      render: (value: number, record) => `${yuan(value)} / ${record.period}`,
    },
    {
      title: '商品配额',
      key: 'products',
      width: 120,
      render: (_, record) => record.quotas?.products ?? '不限',
    },
    {
      title: '成员配额',
      key: 'members',
      width: 120,
      render: (_, record) => record.quotas?.members ?? '不限',
    },
    {
      title: '功能',
      key: 'features',
      render: (_, record) => (
        <Space size={4} wrap>
          {(record.features ?? []).map((feature) => (
            <Tag key={feature}>{feature}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag>
      ),
    },
  ];

  const invoiceColumns: ColumnsType<InvoiceRecord> = [
    { title: '账单号', dataIndex: 'invoice_no' },
    { title: '租户 ID', dataIndex: 'tenant_id', width: 100 },
    {
      title: '金额',
      dataIndex: 'amount_cents',
      width: 120,
      render: (value: number) => yuan(value),
    },
    {
      title: '账期',
      key: 'period',
      render: (_, record) =>
        `${dayjs(record.period_start).format('YYYY-MM-DD')} ~ ${dayjs(record.period_end).format('YYYY-MM-DD')}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag
          color={
            value === 'paid' ? 'success' : value === 'void' ? 'default' : 'gold'
          }
        >
          {value}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          disabled={record.status !== 'pending'}
          onClick={async () => {
            await payInvoice(record.id);
            message.success('账单已支付');
            await refreshAll();
          }}
        >
          标记已付
        </Button>
      ),
    },
  ];

  return (
    <SettingPage
      title="租户管理"
      subTitle="SaaS 租户开通、套餐订阅、用量配额与账单"
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
      <Tabs
        items={[
          {
            key: 'tenants',
            label: '租户',
            children: (
              <Card>
                <Table
                  rowKey="id"
                  loading={tenants.isLoading}
                  columns={tenantColumns}
                  dataSource={tenants.data ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'plans',
            label: '套餐',
            children: (
              <Card
                extra={
                  <Button
                    icon={<PlusOutlined />}
                    onClick={() => setPlanOpen(true)}
                  >
                    新建套餐
                  </Button>
                }
              >
                <Table
                  rowKey="id"
                  loading={plans.isLoading}
                  columns={planColumns}
                  dataSource={plans.data ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'invoices',
            label: '账单',
            children: (
              <Card>
                <Table
                  rowKey="id"
                  loading={invoices.isLoading}
                  columns={invoiceColumns}
                  dataSource={invoices.data ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
        ]}
      />

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
            label="所有者邮箱"
            name="email"
            rules={[{ required: true }]}
          >
            <Input placeholder="owner@acme.com" />
          </Form.Item>
          <Form.Item
            label="所有者昵称"
            name="nickname"
            rules={[{ required: true }]}
          >
            <Input placeholder="Acme Owner" />
          </Form.Item>
          <Form.Item
            label="初始密码"
            name="password"
            rules={[{ required: true, min: 6 }]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
        </Form>
        <span style={{ color: '#8c8c8c' }}>
          新租户会自动订阅免费版并进入试用期。
        </span>
      </Modal>

      <Modal
        title="重命名租户"
        open={!!renameTarget}
        onCancel={() => setRenameTarget(undefined)}
        onOk={handleRename}
        okText="保存"
      >
        <Form form={renameForm} layout="vertical">
          <Form.Item label="租户名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="新建套餐"
        open={planOpen}
        onCancel={() => setPlanOpen(false)}
        onOk={handleCreatePlan}
        okText="创建"
      >
        <Form
          form={planForm}
          layout="vertical"
          initialValues={{ period: 'monthly', trial_days: 14 }}
        >
          <Form.Item
            label="套餐编码"
            name="code"
            rules={[
              {
                required: true,
                pattern: /^[a-z0-9-]+$/,
                message: '仅小写字母/数字/中划线',
              },
            ]}
          >
            <Input placeholder="starter" />
          </Form.Item>
          <Form.Item label="套餐名称" name="name" rules={[{ required: true }]}>
            <Input placeholder="入门版" />
          </Form.Item>
          <Form.Item label="价格（元）" name="price_yuan">
            <InputNumber min={0} step={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="计费周期" name="period">
            <Select
              options={[
                { value: 'monthly', label: '按月' },
                { value: 'yearly', label: '按年' },
              ]}
            />
          </Form.Item>
          <Form.Item label="试用天数" name="trial_days">
            <InputNumber min={0} max={365} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="商品配额（留空为不限）" name="products">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="成员配额（留空为不限）" name="members">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="功能开关" name="features">
            <Select
              mode="tags"
              placeholder="portal / im / finance / commission"
              options={['portal', 'im', 'finance', 'commission'].map(
                (value) => ({
                  value,
                  label: value,
                }),
              )}
            />
          </Form.Item>
        </Form>
        <Space size={6}>
          <WalletOutlined />
          <span style={{ color: '#8c8c8c' }}>
            配额留空表示不限；功能开关用于前端按套餐隐藏模块。
          </span>
        </Space>
      </Modal>
    </SettingPage>
  );
};

export default PlatformTenantsPage;
