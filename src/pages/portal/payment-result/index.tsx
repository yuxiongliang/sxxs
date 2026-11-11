import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from '@umijs/max';
import {
  App,
  Button,
  Card,
  Descriptions,
  Result,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import React, { useState } from 'react';
import { listPortalOrders, mockPayPortalOrder } from '@/services/commerce/api';
import PortalShell from '../components/PortalShell';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const statusMeta = (status: string) => {
  switch (status) {
    case 'paid':
      return {
        status: 'success' as const,
        title: '支付成功',
        icon: <CheckCircleFilled />,
      };
    case 'pending_payment':
      return {
        status: 'warning' as const,
        title: '待支付',
        icon: <ClockCircleOutlined />,
      };
    case 'cancelled':
      return {
        status: 'error' as const,
        title: '订单已取消',
        icon: <CloseCircleFilled />,
      };
    case 'completed':
      return {
        status: 'success' as const,
        title: '交易完成',
        icon: <CheckCircleFilled />,
      };
    default:
      return {
        status: 'info' as const,
        title: status,
        icon: <ClockCircleOutlined />,
      };
  }
};

const PaymentResultPage: React.FC = () => {
  const [params] = useSearchParams();
  const orderId = Number(params.get('orderId'));
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [paying, setPaying] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['portal-orders'],
    queryFn: listPortalOrders,
  });

  const order = data?.find((item) => item.id === orderId);
  const meta = statusMeta(order?.status ?? 'pending_payment');

  const pay = async () => {
    if (!order) return;
    setPaying(true);
    try {
      await mockPayPortalOrder(order.id);
      message.success('支付成功');
      await refetch();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setPaying(false);
    }
  };

  return (
    <PortalShell title="支付结果" maxWidth={880}>
      <Spin spinning={isLoading}>
        <Card>
          {!order && !isLoading ? (
            <Result
              status="404"
              title="订单不存在"
              subTitle="请确认订单号，或回到商城重新下单"
              extra={
                <Button type="primary" onClick={() => navigate('/portal')}>
                  返回商城
                </Button>
              }
            />
          ) : (
            <>
              <Result
                status={meta.status}
                icon={meta.icon}
                title={meta.title}
                subTitle={order ? `订单号 ${order.order_no}` : '正在加载订单…'}
                extra={
                  <Space>
                    {order?.status === 'pending_payment' ? (
                      <Button type="primary" loading={paying} onClick={pay}>
                        立即支付（模拟）
                      </Button>
                    ) : null}
                    <Button onClick={() => navigate('/portal')}>
                      继续购物
                    </Button>
                  </Space>
                }
              />
              {order ? (
                <Descriptions
                  column={1}
                  bordered
                  size="small"
                  style={{ marginTop: 16 }}
                >
                  <Descriptions.Item label="订单号">
                    {order.order_no}
                  </Descriptions.Item>
                  <Descriptions.Item label="订单状态">
                    <Tag color={order.status === 'paid' ? 'green' : 'gold'}>
                      {order.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="应付金额">
                    <Typography.Text
                      strong
                      style={{ color: '#ff4d4f', fontSize: 18 }}
                    >
                      {yuan(order.payable_amount_cents)}
                    </Typography.Text>
                  </Descriptions.Item>
                  {order.created_at ? (
                    <Descriptions.Item label="下单时间">
                      {order.created_at}
                    </Descriptions.Item>
                  ) : null}
                </Descriptions>
              ) : null}
            </>
          )}
        </Card>
      </Spin>
    </PortalShell>
  );
};

export default PaymentResultPage;
