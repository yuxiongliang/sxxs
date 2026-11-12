import {
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
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { PlanRecord } from '@/services/api';
import { createPlan, listPlans } from '@/services/api';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

export default function BillingPlansPage() {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const plans = useQuery({ queryKey: ['platform-plans'], queryFn: listPlans });

  const handleCreate = async () => {
    const values = await form.validateFields();
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
      setOpen(false);
      form.resetFields();
      await plans.refetch();
    } catch (error: any) {
      message.error(error?.message || '创建套餐失败');
    }
  };

  const columns: ColumnsType<PlanRecord> = [
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

  return (
    <PageShell
      title="套餐"
      subTitle="平台售卖的订阅套餐：价格、周期、配额与功能开关"
      icon={<WalletOutlined />}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => plans.refetch()}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setOpen(true)}
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
        title="新建套餐"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={handleCreate}
        okText="创建"
      >
        <Form
          form={form}
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
          <Typography.Text type="secondary">
            配额留空表示不限；功能开关用于前端按套餐隐藏模块。
          </Typography.Text>
        </Space>
      </Modal>
    </PageShell>
  );
}
