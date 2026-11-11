import {
  AccountBookOutlined,
  AuditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import React, { useState } from 'react';
import {
  approvePayout,
  confirmSettlementBatch,
  createCommissionRule,
  createSellerPayout,
  createSettlementBatch,
  deleteCommissionRule,
  getSellerLedger,
  listAdminSellers,
  listCommissionRules,
  listPayouts,
  listSettlementBatches,
  payPayout,
  paySettlementBatch,
  rejectPayout,
} from '@/services/commerce/api';
import type {
  CommissionRuleRecord,
  PayoutRecord,
  SellerRecord,
  SettlementBatchRecord,
} from '@/services/commerce/types';
import SettingPage from '../../system/components/SettingPage';

interface SellerFinance extends SellerRecord {
  balance_cents: number;
  available_cents: number;
  pending_cents: number;
  hold_days: number;
}

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const payoutColor = (status: string) =>
  status === 'paid'
    ? 'green'
    : status === 'approved'
      ? 'blue'
      : status === 'rejected'
        ? 'red'
        : 'gold';

const FinancePage: React.FC = () => {
  const { message } = App.useApp();
  const [ruleOpen, setRuleOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [ruleForm] = Form.useForm();
  const [batchForm] = Form.useForm();

  const {
    data: sellers,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['seller-finance'],
    queryFn: async () => {
      const sellers = await listAdminSellers();
      return Promise.all(
        sellers.map(async (seller) => {
          const ledger = await getSellerLedger(seller.id);
          return {
            ...seller,
            balance_cents: ledger.balance_cents,
            available_cents: ledger.available_cents ?? 0,
            pending_cents: ledger.pending_cents ?? 0,
            hold_days: ledger.hold_days ?? 0,
          };
        }),
      );
    },
  });

  const { data: rules, refetch: refetchRules } = useQuery({
    queryKey: ['commission-rules'],
    queryFn: listCommissionRules,
  });

  const { data: payouts, refetch: refetchPayouts } = useQuery({
    queryKey: ['payouts'],
    queryFn: () => listPayouts(),
  });

  const { data: batches, refetch: refetchBatches } = useQuery({
    queryKey: ['settlement-batches'],
    queryFn: listSettlementBatches,
  });

  const refreshAll = async () => {
    await Promise.all([
      refetch(),
      refetchRules(),
      refetchPayouts(),
      refetchBatches(),
    ]);
  };

  const handlePayout = async (record: SellerFinance) => {
    try {
      await createSellerPayout(record.id);
      message.success('已提交提现申请，等待审核');
      await refreshAll();
    } catch (error: any) {
      message.error(error?.message || '提现申请失败');
    }
  };

  const submitRule = async () => {
    const values = await ruleForm.validateFields();
    try {
      await createCommissionRule({
        name: values.name,
        rate_bps: Math.round((values.rate_percent ?? 0) * 100),
        fixed_fee_cents: Math.round((values.fixed_fee_yuan ?? 0) * 100),
        seller_id: values.seller_id ?? null,
        priority: values.priority ?? 0,
        status: values.status === false ? 'disabled' : 'active',
      });
      message.success('佣金规则已创建');
      setRuleOpen(false);
      ruleForm.resetFields();
      await refetchRules();
    } catch (error: any) {
      message.error(error?.message || '创建失败');
    }
  };

  const submitBatch = async () => {
    const values = await batchForm.validateFields();
    try {
      await createSettlementBatch({
        period_start: values.period[0].toISOString(),
        period_end: values.period[1].toISOString(),
        note: values.note ?? '',
      });
      message.success('结算批次已创建');
      setBatchOpen(false);
      batchForm.resetFields();
      await refetchBatches();
    } catch (error: any) {
      message.error(error?.message || '创建批次失败');
    }
  };

  const sellerColumns: ColumnsType<SellerFinance> = [
    {
      title: '卖家',
      dataIndex: 'display_name',
      render: (_, record) => (
        <Space>
          <AccountBookOutlined style={{ color: '#1677ff' }} />
          <span style={{ fontWeight: 600 }}>{record.display_name}</span>
        </Space>
      ),
    },
    { title: '卖家 ID', dataIndex: 'id', width: 90 },
    {
      title: '可提现',
      dataIndex: 'available_cents',
      width: 130,
      render: (value: number) => (
        <span style={{ fontWeight: 600 }}>{yuan(value)}</span>
      ),
    },
    {
      title: '账期冻结',
      dataIndex: 'pending_cents',
      width: 130,
      render: (value: number) => (
        <Tooltip title="订单完成后需经过账期才可提现">
          <span style={{ color: '#8c8c8c' }}>{yuan(value)}</span>
        </Tooltip>
      ),
    },
    {
      title: '总额',
      dataIndex: 'balance_cents',
      width: 120,
      render: (value: number) => yuan(value),
    },
    {
      title: '账期',
      dataIndex: 'hold_days',
      width: 90,
      render: (value: number) => `${value} 天`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag>
      ),
    },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          disabled={record.available_cents <= 0}
          onClick={() => handlePayout(record)}
        >
          申请提现
        </Button>
      ),
    },
  ];

  const ruleColumns: ColumnsType<CommissionRuleRecord> = [
    { title: '名称', dataIndex: 'name' },
    {
      title: '费率',
      dataIndex: 'rate_bps',
      width: 110,
      render: (value: number) => `${(value / 100).toFixed(2)}%`,
    },
    {
      title: '固定费',
      dataIndex: 'fixed_fee_cents',
      width: 110,
      render: (value: number) => yuan(value),
    },
    {
      title: '作用域',
      key: 'scope',
      width: 160,
      render: (_, record) =>
        record.seller_id
          ? `卖家 #${record.seller_id}`
          : record.category_id
            ? `分类 #${record.category_id}`
            : '租户默认',
    },
    { title: '优先级', dataIndex: 'priority', width: 90 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag>
      ),
    },
    {
      title: '操作',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title="删除该佣金规则？"
          onConfirm={async () => {
            await deleteCommissionRule(record.id);
            message.success('已删除');
            await refetchRules();
          }}
        >
          <Button type="link" danger size="small">
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const payoutColumns: ColumnsType<PayoutRecord> = [
    { title: '申请 ID', dataIndex: 'id', width: 90 },
    { title: '卖家 ID', dataIndex: 'seller_id', width: 90 },
    {
      title: '金额',
      dataIndex: 'amount_cents',
      width: 130,
      render: (value: number) => (
        <span style={{ fontWeight: 600 }}>{yuan(value)}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: string) => <Tag color={payoutColor(value)}>{value}</Tag>,
    },
    {
      title: '驳回原因',
      dataIndex: 'reject_reason',
      render: (value: string) => value || '-',
    },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space size={2}>
          <Button
            type="link"
            size="small"
            disabled={record.status !== 'pending'}
            onClick={async () => {
              await approvePayout(record.id);
              message.success('已审核通过');
              await refreshAll();
            }}
          >
            通过
          </Button>
          <Button
            type="link"
            size="small"
            danger
            disabled={record.status !== 'pending'}
            onClick={async () => {
              const reason = window.prompt('驳回原因') ?? '';
              await rejectPayout(record.id, reason);
              message.success('已驳回');
              await refreshAll();
            }}
          >
            驳回
          </Button>
          <Button
            type="link"
            size="small"
            disabled={record.status !== 'approved'}
            onClick={async () => {
              await payPayout(record.id);
              message.success('已打款');
              await refreshAll();
            }}
          >
            打款
          </Button>
        </Space>
      ),
    },
  ];

  const batchColumns: ColumnsType<SettlementBatchRecord> = [
    { title: '批次号', dataIndex: 'batch_no' },
    {
      title: '账期',
      key: 'period',
      render: (_, record) =>
        `${dayjs(record.period_start).format('YYYY-MM-DD')} ~ ${dayjs(record.period_end).format('YYYY-MM-DD')}`,
    },
    {
      title: '金额',
      dataIndex: 'total_amount_cents',
      width: 130,
      render: (value: number) => yuan(value),
    },
    { title: '提现笔数', dataIndex: 'payout_count', width: 100 },
    { title: '卖家数', dataIndex: 'seller_count', width: 90 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: string) => (
        <Tag
          color={
            value === 'paid' ? 'green' : value === 'confirmed' ? 'blue' : 'gold'
          }
        >
          {value}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space size={2}>
          <Button
            type="link"
            size="small"
            disabled={record.status !== 'draft'}
            onClick={async () => {
              await confirmSettlementBatch(record.id);
              message.success('批次已确认');
              await refetchBatches();
            }}
          >
            确认
          </Button>
          <Button
            type="link"
            size="small"
            disabled={record.status !== 'confirmed'}
            onClick={async () => {
              await paySettlementBatch(record.id);
              message.success('批次已打款');
              await refreshAll();
            }}
          >
            打款
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <SettingPage
      title="财务结算"
      subTitle="佣金规则、提现审核、账期冻结与结算批次"
      icon={<AccountBookOutlined />}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refreshAll()}>
            刷新
          </Button>
        </Space>
      }
    >
      <Tabs
        items={[
          {
            key: 'sellers',
            label: '卖家余额',
            children: (
              <Card>
                <Table
                  rowKey="id"
                  loading={isLoading}
                  columns={sellerColumns}
                  dataSource={sellers ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'rules',
            label: '佣金规则',
            children: (
              <Card
                extra={
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => {
                      ruleForm.resetFields();
                      setRuleOpen(true);
                    }}
                  >
                    新增规则
                  </Button>
                }
              >
                <Table
                  rowKey="id"
                  columns={ruleColumns}
                  dataSource={rules ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'payouts',
            label: '提现审核',
            children: (
              <Card>
                <Table
                  rowKey="id"
                  columns={payoutColumns}
                  dataSource={payouts ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'batches',
            label: '结算批次',
            children: (
              <Card
                extra={
                  <Button
                    type="primary"
                    icon={<AuditOutlined />}
                    onClick={() => {
                      batchForm.resetFields();
                      setBatchOpen(true);
                    }}
                  >
                    生成批次
                  </Button>
                }
              >
                <Table
                  rowKey="id"
                  columns={batchColumns}
                  dataSource={batches ?? []}
                  pagination={false}
                />
              </Card>
            ),
          },
        ]}
      />

      <Modal
        title="新增佣金规则"
        open={ruleOpen}
        onCancel={() => setRuleOpen(false)}
        onOk={submitRule}
        okText="保存"
      >
        <Form
          form={ruleForm}
          layout="vertical"
          initialValues={{ priority: 0, status: true }}
        >
          <Form.Item
            label="规则名称"
            name="name"
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="例如：数码类 3%" />
          </Form.Item>
          <Form.Item
            label="费率（%）"
            name="rate_percent"
            rules={[{ required: true, message: '请输入费率' }]}
          >
            <InputNumber
              min={0}
              max={100}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label="固定费用（元）" name="fixed_fee_yuan">
            <InputNumber min={0} step={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="卖家 ID（留空表示租户默认）" name="seller_id">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="优先级" name="priority">
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="启用" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
        <Space size={6}>
          <SettingOutlined />
          <span style={{ color: '#8c8c8c' }}>
            作用域越具体优先级越高：卖家+分类 &gt; 卖家 &gt; 分类 &gt;
            租户默认。
          </span>
        </Space>
      </Modal>

      <Modal
        title="生成结算批次"
        open={batchOpen}
        onCancel={() => setBatchOpen(false)}
        onOk={submitBatch}
        okText="生成"
      >
        <Form form={batchForm} layout="vertical">
          <Form.Item
            label="账期区间"
            name="period"
            rules={[{ required: true, message: '请选择账期区间' }]}
          >
            <DatePicker.RangePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="备注" name="note">
            <Input.TextArea rows={2} placeholder="选填" />
          </Form.Item>
        </Form>
        <span style={{ color: '#8c8c8c' }}>
          只会纳入「已审核通过且未入批次」的提现申请。
        </span>
      </Modal>
    </SettingPage>
  );
};

export default FinancePage;
