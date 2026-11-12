import { ReloadOutlined, WalletOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { CommissionRow } from '@/services/api';
import { getCommissionReport } from '@/services/api';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;
const bpsToPercent = (bps: number) =>
  `${(bps / 100).toFixed(bps % 100 === 0 ? 0 : 2)}%`;

const PERIOD_LABEL: Record<string, string> = {
  lifetime: '永久买断',
  custom: '自定义档期',
  monthly: '按月',
  yearly: '按年',
};

export default function CommissionReportPage() {
  const [month, setMonth] = useState(dayjs());
  const report = useQuery({
    queryKey: ['commission-report', month.format('YYYY-MM')],
    queryFn: () => getCommissionReport(month.format('YYYY-MM')),
  });

  const columns: ColumnsType<CommissionRow> = [
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
    {
      title: '业务类目',
      width: 160,
      render: (_, record) =>
        record.service_category ? (
          <Tag color="blue">{record.service_category.name}</Tag>
        ) : (
          <Tag color="red">未分类</Tag>
        ),
    },
    {
      title: '套餐周期',
      width: 120,
      render: (_, record) =>
        record.plan_period
          ? (PERIOD_LABEL[record.plan_period] ?? record.plan_period)
          : '—',
    },
    {
      title: '当月 GMV',
      dataIndex: 'gmv_cents',
      width: 140,
      align: 'right',
      render: (value: number) => yuan(value),
    },
    {
      title: '抽佣比例',
      dataIndex: 'rate_bps',
      width: 110,
      align: 'right',
      render: (value: number) => (value > 0 ? bpsToPercent(value) : '0%'),
    },
    {
      title: '应抽佣',
      dataIndex: 'commission_cents',
      width: 130,
      align: 'right',
      render: (value: number, record) =>
        record.waived ? (
          <Tag color="gold">豁免（买断/档期）</Tag>
        ) : (
          <Typography.Text strong>{yuan(value)}</Typography.Text>
        ),
    },
  ];

  const totals = report.data;

  return (
    <PageShell
      title="抽佣台账"
      subTitle="按月汇总：当月已支付 GMV × 租户所属类目比例；买断/自定义档期租户豁免"
      icon={<WalletOutlined />}
      extra={
        <Space>
          <DatePicker
            picker="month"
            allowClear={false}
            value={month}
            onChange={(value) => value && setMonth(value)}
          />
          <Button icon={<ReloadOutlined />} onClick={() => report.refetch()}>
            刷新
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="这里只是台账，不会自动扣款"
        description="基数取租户当月已支付订单金额（paid_at 落在当月）；比例取租户所属业务类目；买断（lifetime）与自定义档期（custom）套餐恒为 0。真正收款需要单独的账务流程。"
      />

      <Card style={{ marginBottom: 16 }}>
        <Space size={48}>
          <Statistic title="月份" value={totals?.month ?? '—'} />
          <Statistic
            title="当月 GMV 合计"
            value={yuan(totals?.total_gmv_cents ?? 0)}
          />
          <Statistic
            title="应抽佣合计"
            value={yuan(totals?.total_commission_cents ?? 0)}
            styles={{ content: { color: '#cf1322' } }}
          />
        </Space>
      </Card>

      <Card>
        <Table<CommissionRow>
          rowKey="tenant_id"
          size="small"
          loading={report.isLoading}
          columns={columns}
          dataSource={totals?.rows ?? []}
          pagination={false}
        />
      </Card>
    </PageShell>
  );
}
