import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from '@umijs/max';
import { Button, Card, Descriptions, Empty, Skeleton, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { getPortalOrderDetail } from '@/services/commerce/api';
import type { PortalOrderDetail } from '@/services/commerce/api';
import PortalShell from '../../components/PortalShell';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const STATUS_COLOR: Record<string, string> = {
  pending_payment: 'orange',
  paid: 'blue',
  partially_shipped: 'cyan',
  shipped: 'geekblue',
  completed: 'green',
  cancelled: 'default',
  refunded: 'red',
};

/** 订单详情（新增页面；接口 `GET /portal/orders/{id}` 已有，按买家作用域） */
export default function PortalOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const orderId = Number(id);
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['portal-order-detail', orderId],
    queryFn: () => getPortalOrderDetail(orderId),
    enabled: Number.isFinite(orderId),
  });

  const columns: ColumnsType<PortalOrderDetail['items'][number]> = [
    { title: '商品', dataIndex: 'product_name' },
    { title: '规格', dataIndex: 'sku_name', width: 160 },
    {
      title: '单价',
      dataIndex: 'price_cents',
      width: 120,
      align: 'right',
      render: (value: number) => yuan(value),
    },
    { title: '数量', dataIndex: 'quantity', width: 90, align: 'right' },
  ];

  return (
    <PortalShell title="订单详情">
      <Card
        extra={
          <Button onClick={() => navigate('/portal/orders')}>返回列表</Button>
        }
      >
        {isLoading ? (
          <Skeleton active />
        ) : isError || !data ? (
          <Empty description="订单不存在或不属于当前账号" />
        ) : (
          <>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="订单号">
                {data.order_no}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLOR[data.status] ?? 'default'}>
                  {data.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="应付金额">
                {yuan(data.payable_amount_cents)}
              </Descriptions.Item>
              <Descriptions.Item label="卖家订单数">
                {data.seller_orders.length}
              </Descriptions.Item>
            </Descriptions>

            <Table
              style={{ marginTop: 16 }}
              rowKey={(record) => `${record.product_name}-${record.sku_name}`}
              columns={columns}
              dataSource={data.items}
              pagination={false}
              size="small"
            />
          </>
        )}
      </Card>
    </PortalShell>
  );
}
