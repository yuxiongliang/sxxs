import { ProfileOutlined, ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import {
  cancelOrder,
  getAdminOrderDetail,
  listAdminOrders,
  mockPayOrder,
  refundSellerOrder,
  shipSellerOrder,
} from '@/services/commerce/api';
import type {
  OrderDetail,
  OrderRecord,
  SellerOrderRecord,
} from '@/services/commerce/types';
import { labelOf, ORDER_STATUS } from '@/utils/labels';
import SettingPage from '../../system/components/SettingPage';

const statusColor = (status: string) =>
  status === 'paid' || status === 'completed'
    ? 'success'
    : status === 'pending_payment'
      ? 'gold'
      : status === 'refunded'
        ? 'red'
        : 'default';

const OrderManagementPage: React.FC = () => {
  const { message } = App.useApp();
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<OrderDetail>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [shipOpen, setShipOpen] = useState(false);
  const [refundOpen, setRefundOpen] = useState(false);
  const [selected, setSelected] = useState<SellerOrderRecord>();
  const [shipForm] = Form.useForm();
  const [refundForm] = Form.useForm();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-orders'],
    queryFn: listAdminOrders,
  });

  const openDetail = async (record: OrderRecord) => {
    setDetailOpen(true);
    setDetailLoading(true);
    try {
      setDetail(await getAdminOrderDetail(record.id));
    } catch (error: any) {
      message.error(error?.message || '加载订单详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const reloadDetail = async () => {
    if (!detail) return;
    setDetail(await getAdminOrderDetail(detail.id));
    refetch();
  };

  const handleShip = async () => {
    if (!selected) return;
    const values = await shipForm.validateFields();
    await shipSellerOrder(selected.id, values);
    message.success('发货成功');
    setShipOpen(false);
    shipForm.resetFields();
    await reloadDetail();
  };

  const handleRefund = async () => {
    if (!selected) return;
    const values = await refundForm.validateFields();
    await refundSellerOrder(selected.id, {
      amount_cents: Math.round(values.amount * 100),
      reason: values.reason,
    });
    message.success('退款成功');
    setRefundOpen(false);
    refundForm.resetFields();
    await reloadDetail();
  };

  const columns: ColumnsType<OrderRecord> = [
    {
      title: '订单号',
      dataIndex: 'order_no',
      render: (value: string) => (
        <span style={{ fontWeight: 600 }}>{value}</span>
      ),
    },
    { title: '买家 ID', dataIndex: 'buyer_id', width: 100 },
    {
      title: '金额',
      dataIndex: 'payable_amount_cents',
      width: 140,
      render: (value: number) => `¥${(value / 100).toFixed(2)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 160,
      render: (value: string) => (
        <Tag color={statusColor(value)}>{labelOf(ORDER_STATUS, value)}</Tag>
      ),
    },
    {
      title: '操作',
      width: 260,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" onClick={() => openDetail(record)}>
            详情
          </Button>
          {record.status === 'pending_payment' && (
            <>
              <Button
                type="link"
                size="small"
                onClick={async () => {
                  await mockPayOrder(record.id);
                  message.success('模拟支付成功');
                  refetch();
                }}
              >
                模拟支付
              </Button>
              <Button
                type="link"
                size="small"
                danger
                onClick={async () => {
                  await cancelOrder(record.id);
                  message.success('订单已取消');
                  refetch();
                }}
              >
                取消
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  const sellerColumns: ColumnsType<SellerOrderRecord> = [
    { title: '卖家单 ID', dataIndex: 'id', width: 100 },
    { title: '卖家 ID', dataIndex: 'seller_id', width: 100 },
    {
      title: '商品金额',
      dataIndex: 'goods_amount_cents',
      render: (value: number) => `¥${(value / 100).toFixed(2)}`,
    },
    {
      title: '佣金',
      dataIndex: 'commission_amount_cents',
      render: (value: number) => `¥${(value / 100).toFixed(2)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (value: string) => (
        <Tag color={statusColor(value)}>{labelOf(ORDER_STATUS, value)}</Tag>
      ),
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space>
          {['paid', 'processing'].includes(record.status) && (
            <Button
              type="link"
              size="small"
              onClick={() => {
                setSelected(record);
                setShipOpen(true);
              }}
            >
              发货
            </Button>
          )}
          {['paid', 'shipped', 'completed'].includes(record.status) && (
            <Button
              type="link"
              size="small"
              danger
              onClick={() => {
                setSelected(record);
                refundForm.setFieldsValue({
                  amount: record.goods_amount_cents / 100,
                });
                setRefundOpen(true);
              }}
            >
              退款
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <SettingPage
      title="订单管理"
      subTitle="C2C 市场订单与卖家拆单"
      icon={<ProfileOutlined />}
      extra={
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
          刷新
        </Button>
      }
    >
      <Card>
        <Table
          rowKey="id"
          loading={isLoading}
          columns={columns}
          dataSource={data ?? []}
          pagination={false}
        />
      </Card>

      <Drawer
        title={detail ? `订单 ${detail.order_no}` : '订单详情'}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        size={880}
        loading={detailLoading}
      >
        {detail && (
          <Space orientation="vertical" size={20} style={{ display: 'flex' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="订单号">
                {detail.order_no}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColor(detail.status)}>{detail.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="买家 ID">
                {detail.buyer_id}
              </Descriptions.Item>
              <Descriptions.Item label="金额">
                ¥{(detail.payable_amount_cents / 100).toFixed(2)}
              </Descriptions.Item>
            </Descriptions>
            <Card size="small" title="卖家拆单">
              <Table
                rowKey="id"
                size="small"
                columns={sellerColumns}
                dataSource={detail.seller_orders}
                pagination={false}
              />
            </Card>
            <Card size="small" title="商品明细">
              <Table
                rowKey="id"
                size="small"
                pagination={false}
                dataSource={detail.items}
                columns={[
                  { title: '商品', dataIndex: 'product_name' },
                  { title: 'SKU', dataIndex: 'sku_name' },
                  {
                    title: '单价',
                    dataIndex: 'price_cents',
                    render: (v: number) => `¥${(v / 100).toFixed(2)}`,
                  },
                  { title: '数量', dataIndex: 'quantity' },
                  {
                    title: '小计',
                    dataIndex: 'subtotal_cents',
                    render: (v: number) => `¥${(v / 100).toFixed(2)}`,
                  },
                ]}
              />
            </Card>
          </Space>
        )}
      </Drawer>

      <Modal
        title="卖家发货"
        open={shipOpen}
        onCancel={() => setShipOpen(false)}
        onOk={handleShip}
        destroyOnHidden
      >
        <Form form={shipForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="物流公司"
            name="carrier"
            rules={[{ required: true, message: '请输入物流公司' }]}
          >
            <Input placeholder="顺丰 / 中通 / 圆通" />
          </Form.Item>
          <Form.Item
            label="运单号"
            name="tracking_no"
            rules={[{ required: true, message: '请输入运单号' }]}
          >
            <Input placeholder="SF123456789" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="订单退款"
        open={refundOpen}
        onCancel={() => setRefundOpen(false)}
        onOk={handleRefund}
        destroyOnHidden
      >
        <Form form={refundForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="退款金额（元）"
            name="amount"
            rules={[{ required: true, message: '请输入退款金额' }]}
          >
            <InputNumber min={0.01} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="退款原因" name="reason">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </SettingPage>
  );
};

export default OrderManagementPage;
