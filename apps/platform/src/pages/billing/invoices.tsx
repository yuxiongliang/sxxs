import { ReloadOutlined, WalletOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { App, Button, Card, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import PageShell from '@/components/PageShell';
import type { InvoiceRecord } from '@/services/api';
import { listInvoices, payInvoice } from '@/services/api';
import { INVOICE_STATUS, labelOf } from '@/utils/labels';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

export default function BillingInvoicesPage() {
  const { message } = App.useApp();
  const invoices = useQuery({
    queryKey: ['platform-invoices'],
    queryFn: () => listInvoices(),
  });

  const columns: ColumnsType<InvoiceRecord> = [
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
          {labelOf(INVOICE_STATUS, value)}
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
            await invoices.refetch();
          }}
        >
          标记已付
        </Button>
      ),
    },
  ];

  return (
    <PageShell
      title="账单"
      subTitle="订阅账单与收款状态；「标记已付」用于线下打款后手工核销"
      icon={<WalletOutlined />}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => invoices.refetch()}>
            刷新
          </Button>
        </Space>
      }
    >
      <Card>
        <Table
          rowKey="id"
          loading={invoices.isLoading}
          columns={columns}
          dataSource={invoices.data ?? []}
          pagination={false}
        />
      </Card>
    </PageShell>
  );
}
