import { useQuery } from '@tanstack/react-query';
import { useNavigate } from '@umijs/max';
import { App, Button, Card, Empty, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  confirmPortalOrder,
  listPortalOrders,
  mockPayPortalOrder,
} from '@/services/commerce/api';
import type { PortalOrder } from '@/services/commerce/types';
import { labelOf, ORDER_STATUS } from '@/utils/labels';
import PortalShell from '../components/PortalShell';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const STATUS_COLOR: Record<string, string> = {
  pending_payment: 'orange',
  paid: 'blue',
  shipped: 'geekblue',
  completed: 'green',
  cancelled: 'default',
  refunded: 'red',
};

/** 我的订单（从原 /portal 的 Tab 迁出为独立页面） */
export default function PortalOrdersPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['portal-orders'],
    queryFn: listPortalOrders,
  });
  const orders = data ?? [];

  const columns: ColumnsType<PortalOrder> = [
    {
      title: '订单号',
      dataIndex: 'order_no',
      render: (value: string, record) => (
        <a onClick={() => navigate(`/portal/orders/${record.id}`)}>{value}</a>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 120,
      render: (value: string) => (
        <Tag color={STATUS_COLOR[value] ?? 'default'}>
          {labelOf(ORDER_STATUS, value)}
        </Tag>
      ),
    },
    {
      title: '金额',
      dataIndex: 'payable_amount_cents',
      width: 120,
      align: 'right',
      render: (value: number) => yuan(value),
    },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            onClick={() => navigate(`/portal/orders/${record.id}`)}
          >
            详情
          </Button>
          {record.status === 'pending_payment' ? (
            <Button
              size="small"
              type="primary"
              onClick={async () => {
                await mockPayPortalOrder(record.id);
                message.success('支付成功');
                refetch();
              }}
            >
              模拟支付
            </Button>
          ) : null}
          {record.status === 'shipped' ? (
            <Button
              size="small"
              onClick={async () => {
                await confirmPortalOrder(record.id);
                message.success('已确认收货');
                refetch();
              }}
            >
              确认收货
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <PortalShell title="我的订单">
      <Card>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={orders}
          loading={isLoading}
          pagination={false}
          locale={{ emptyText: <Empty description="还没有订单" /> }}
        />
        <Typography.Paragraph
          type="secondary"
          style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}
        >
          订单详情可在「详情」中查看；需要继续挑选商品请回到前台商品页。
        </Typography.Paragraph>
      </Card>
    </PortalShell>
  );
}
