import {
  PlusOutlined,
  ReloadOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { PlanRecord } from '@/services/api';
import { createPlan, deletePlan, listPlans, updatePlan } from '@/services/api';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

function periodLabel(record: PlanRecord): string {
  if (record.period === 'lifetime') return '永久买断';
  if (record.period === 'custom') return '自定义档期';
  if (record.duration_months) return `${record.duration_months} 个月`;
  return record.period === 'yearly' ? '12 个月' : '1 个月';
}

interface PlanFormValues {
  code?: string;
  name: string;
  price_yuan: number;
  duration_months?: number | null;
}

export default function BillingPlansPage() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<PlanFormValues>();
  const [editing, setEditing] = useState<PlanRecord | null>(null);
  const [open, setOpen] = useState(false);

  const plans = useQuery({ queryKey: ['platform-plans'], queryFn: listPlans });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['platform-plans'] });
    queryClient.invalidateQueries({ queryKey: ['platform-tenants-plan'] });
  };

  const save = useMutation({
    mutationFn: async (values: PlanFormValues) => {
      const payload = {
        name: values.name,
        price_cents: Math.round((values.price_yuan ?? 0) * 100),
        duration_months: values.duration_months ?? null,
      };
      if (editing) return updatePlan(editing.id, payload);
      return createPlan({ ...payload, code: values.code as string });
    },
    onSuccess: () => {
      message.success(editing ? '套餐已更新' : '套餐已创建');
      setOpen(false);
      setEditing(null);
      form.resetFields();
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const toggleStatus = useMutation({
    mutationFn: (record: PlanRecord) =>
      updatePlan(record.id, {
        status: record.status === 'active' ? 'archived' : 'active',
      }),
    onSuccess: (record) => {
      message.success(record.status === 'active' ? '套餐已上架' : '套餐已下架');
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (record: PlanRecord) => deletePlan(record.id),
    onSuccess: () => {
      message.success('套餐已删除');
      refresh();
    },
    // 被订阅引用时后端 409，直接展示原因（提示改为下架）
    onError: (error: Error) => message.error(error.message),
  });

  const columns: ColumnsType<PlanRecord> = [
    { title: '名称', dataIndex: 'name', width: 180 },
    {
      title: '价格',
      dataIndex: 'price_cents',
      width: 140,
      render: (value: number) => yuan(value),
    },
    {
      title: '时长',
      key: 'duration',
      width: 140,
      render: (_, record) => periodLabel(record),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'success' : 'default'}>
          {value === 'active' ? '在售' : '已下架'}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space size={2}>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setEditing(record);
              form.setFieldsValue({
                name: record.name,
                price_yuan: record.price_cents / 100,
                duration_months: record.duration_months ?? undefined,
              });
              setOpen(true);
            }}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => toggleStatus.mutate(record)}
          >
            {record.status === 'active' ? '下架' : '上架'}
          </Button>
          <Popconfirm
            title="删除后不可恢复；若已有租户订阅会被拒绝（改下架）。确认？"
            onConfirm={() => remove.mutate(record)}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="套餐"
      subTitle="平台售卖的套餐：价格、时长与上下架（买断/档期套餐不带试用）"
      icon={<WalletOutlined />}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => plans.refetch()}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null);
              form.resetFields();
              // 默认留空 = 永久买断（买断不留试用）；要限期套餐再填月数
              form.setFieldsValue({
                price_yuan: 0,
                duration_months: undefined,
              });
              setOpen(true);
            }}
          >
            新建套餐
          </Button>
        </Space>
      }
    >
      <Card>
        <Table
          rowKey="id"
          loading={plans.isLoading}
          columns={columns}
          dataSource={plans.data ?? []}
          pagination={false}
        />
      </Card>

      <Modal
        title={editing ? `编辑套餐 ${editing.name}` : '新建套餐'}
        open={open}
        onCancel={() => {
          setOpen(false);
          setEditing(null);
        }}
        onOk={() => form.submit()}
        confirmLoading={save.isPending}
        okText="保存"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => save.mutate(values)}
        >
          {editing ? null : (
            <Form.Item
              name="code"
              label="套餐编码"
              rules={[
                {
                  required: true,
                  pattern: /^[a-z0-9-]+$/,
                  message: '仅小写字母/数字/中划线',
                },
              ]}
              extra="只用于内部识别，列表里不展示；创建后不可修改。"
            >
              <Input placeholder="yearly-12" />
            </Form.Item>
          )}
          <Form.Item name="name" label="套餐名称" rules={[{ required: true }]}>
            <Input placeholder="包年版" />
          </Form.Item>
          <Form.Item
            name="price_yuan"
            label="价格（元）"
            rules={[{ required: true }]}
          >
            <InputNumber min={0} step={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="duration_months"
            label="时长（月）"
            extra="填 N 就按 N × 30 天计算订阅有效期；永久买断套餐请留空。"
          >
            <InputNumber
              min={1}
              max={120}
              style={{ width: '100%' }}
              placeholder="12"
            />
          </Form.Item>
        </Form>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          提示：永久买断与自定义档期套餐不能设置试用；被租户订阅的套餐不能删除，只能下架。
        </Typography.Text>
      </Modal>
    </PageShell>
  );
}
