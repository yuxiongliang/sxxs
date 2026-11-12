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
  assignTenantCategory,
  createTenant,
  listPlans,
  listPlatformUsers,
  listServiceCategories,
  listTenantOverview,
  listTenantsWithPlan,
  renewTenant,
  resumeTenant,
  subscribeTenant,
  suspendTenant,
  updateTenant,
} from '@/services/api';
import { labelOf, SUBSCRIPTION_STATUS, TENANT_STATUS } from '@/utils/labels';
import TenantDomainDrawer from './DomainDrawer';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

/** bps → 百分比：500 → 5% */
const bpsToPercent = (bps: number) =>
  `${(bps / 100).toFixed(bps % 100 === 0 ? 0 : 2)}%`;

const statusColor = (status?: string) =>
  status === 'active'
    ? 'success'
    : status === 'trialing'
      ? 'blue'
      : status === 'suspended' || status === 'past_due'
        ? 'red'
        : 'default';

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
  const [categoryTarget, setCategoryTarget] = useState<TenantWithPlan | null>(
    null,
  );
  const [createForm] = Form.useForm();
  const [renameForm] = Form.useForm();
  const [categoryForm] = Form.useForm();
  const [ownerKeyword, setOwnerKeyword] = useState('');

  const tenants = useQuery({
    queryKey: ['platform-tenants-plan'],
    queryFn: listTenantsWithPlan,
  });
  const plans = useQuery({ queryKey: ['platform-plans'], queryFn: listPlans });
  // 业务类目：决定抽佣比例，开通租户与「归类」都要用
  // 开通租户时的管理员候选：按关键词实时检索全站用户
  const ownerCandidates = useQuery({
    queryKey: ['owner-picker', ownerKeyword],
    queryFn: () =>
      listPlatformUsers({ pageSize: 20, keyword: ownerKeyword || undefined }),
    enabled: createOpen,
  });
  const categories = useQuery({
    queryKey: ['service-categories'],
    queryFn: () => listServiceCategories(),
  });
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
    await Promise.all([
      tenants.refetch(),
      plans.refetch(),
      overview.refetch(),
      categories.refetch(),
    ]);
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
      // 管理员用户ID（对外编号），放在最前面便于对账
      title: '用户ID',
      key: 'owner_public_id',
      width: 250,
      render: (_, record) =>
        record.owner ? (
          <Typography.Text copyable>{record.owner.public_id}</Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      // 管理员登录用户名；租户名与 slug 保留在第二行，信息不丢
      title: '用户名',
      key: 'owner_username',
      width: 240,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Space>
            <ClusterOutlined style={{ color: '#1677ff' }} />
            <strong>{record.owner?.username ?? '—'}</strong>
          </Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.name} · {record.slug}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={statusColor(value)}>{labelOf(TENANT_STATUS, value)}</Tag>
      ),
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
            {record.plan?.period === 'lifetime'
              ? '永久（买断）'
              : record.subscription
                ? `${labelOf(SUBSCRIPTION_STATUS, record.subscription.status)} · 剩 ${record.days_left ?? 0} 天`
                : '无订阅记录'}
          </Typography.Text>
        </Space>
      ),
    },

    {
      title: '类目 / 抽佣',
      key: 'service_category',
      width: 170,
      render: (_, record) =>
        record.service_category ? (
          <Space orientation="vertical" size={0}>
            <Typography.Text>{record.service_category.name}</Typography.Text>
            {record.service_category.commission_bps > 0 ? (
              <Tag color="gold">
                抽佣 {bpsToPercent(record.service_category.commission_bps)}
              </Tag>
            ) : (
              <Tag>不抽佣</Tag>
            )}
          </Space>
        ) : (
          <Tag color="red">未分类</Tag>
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
              setCategoryTarget(record);
              categoryForm.setFieldsValue({
                service_category_id: record.service_category?.id ?? undefined,
              });
            }}
          >
            归类
          </Button>
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
            label="租户管理员"
            name="owner_user_id"
            rules={[{ required: true, message: '请选择租户管理员' }]}
            extra="按手机号 / 邮箱 / 用户ID / 用户名搜索站内已有用户；选中后直接挂成该租户的管理员，不新建账号。"
          >
            <Select
              showSearch={{
                filterOption: false,
                onSearch: (value: string) => setOwnerKeyword(value.trim()),
              }}
              placeholder="输入手机号 / 邮箱 / 用户ID / 用户名"
              loading={ownerCandidates.isFetching}
              options={(ownerCandidates.data?.list ?? []).map((item) => ({
                value: item.id,
                label: `${item.username}（${item.public_id}）`,
              }))}
            />
          </Form.Item>
          <Form.Item
            label="服务类目"
            name="service_category_id"
            extra="决定抽佣比例；留空表示暂未分类（不抽佣），之后可以在列表里补。"
          >
            <Select
              allowClear
              placeholder="未分类"
              options={(categories.data ?? []).map((item) => ({
                value: item.id,
                label:
                  item.commission_bps > 0
                    ? `${item.name}（抽佣 ${bpsToPercent(item.commission_bps)}）`
                    : `${item.name}（不抽佣）`,
              }))}
            />
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

      <Modal
        title="归类到服务类目"
        open={Boolean(categoryTarget)}
        onCancel={() => setCategoryTarget(null)}
        onOk={async () => {
          if (!categoryTarget) return;
          try {
            const value = categoryForm.getFieldValue('service_category_id') as
              | number
              | undefined;
            await assignTenantCategory(categoryTarget.id, value ?? null);
            message.success('归类已更新');
            setCategoryTarget(null);
            await refreshAll();
          } catch (error: any) {
            message.error(error?.message || '归类失败');
          }
        }}
        okText="保存"
      >
        <Form form={categoryForm} layout="vertical">
          <Form.Item name="service_category_id" label="服务类目">
            <Select
              allowClear
              placeholder="未分类（不抽佣）"
              options={(categories.data ?? []).map((item) => ({
                value: item.id,
                label:
                  item.commission_bps > 0
                    ? `${item.name}（抽佣 ${bpsToPercent(item.commission_bps)}）`
                    : `${item.name}（不抽佣）`,
              }))}
            />
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
