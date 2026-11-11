import { ShoppingCartOutlined, UserOutlined } from '@ant-design/icons';
import { getSellerApplication } from '@/services/commerce/api';
import { useQuery } from '@tanstack/react-query';
import { useModel } from '@umijs/max';
import {
  App,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Space,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import React, { useState } from 'react';
import {
  addCartItem,
  confirmPortalOrder,
  createPortalOrder,
  listPortalOrders,
  listPortalProducts,
  mockPayPortalOrder,
} from '@/services/commerce/api';
import type { PortalProduct } from '@/services/commerce/types';

const statusColor = (status: string) =>
  status === 'paid' || status === 'completed'
    ? 'success'
    : status === 'pending_payment'
      ? 'gold'
      : 'default';

const PortalPage: React.FC = () => {
  const { message } = App.useApp();
  const { initialState } = useModel('@@initialState');
  const [product, setProduct] = useState<PortalProduct>();
  const [open, setOpen] = useState(false);
  const [buyForm] = Form.useForm();

  const { data: products, isLoading } = useQuery({
    queryKey: ['portal-products'],
    queryFn: listPortalProducts,
  });
  const { data: orders, refetch: refetchOrders } = useQuery({
    queryKey: ['portal-orders'],
    queryFn: listPortalOrders,
  });

  const openBuy = (item: PortalProduct) => {
    setProduct(item);
    buyForm.setFieldsValue({
      quantity: 1,
      receiver_name: initialState?.currentUser?.name,
      receiver_phone: '13800000000',
      address: '演示收货地址',
    });
    setOpen(true);
  };

  const handleBuy = async () => {
    if (!product?.sku) return;
    const values = await buyForm.validateFields();
    await createPortalOrder({
      sku_id: product.sku.id,
      quantity: values.quantity,
      receiver_name: values.receiver_name,
      receiver_phone: values.receiver_phone,
      receiver_address: { detail: values.address },
    });
    message.success('下单成功，请到我的订单查看');
    setOpen(false);
    refetchOrders();
  };

  const { data: application } = useQuery({
    queryKey: ['seller-application'],
    queryFn: getSellerApplication,
    retry: false,
  });
  const sellerNavLabel = !application?.has_seller
    ? '申请开店'
    : application.status === 'pending'
      ? '我的店铺（审核中）'
      : '我的店铺';

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <div
        style={{
          background: '#1677ff',
          color: '#fff',
          padding: '20px 48px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 700 }}>C2C 商城</div>
        <Space size={20}>
          <a href="/portal/cart" style={{ color: '#fff' }}>
            <ShoppingCartOutlined /> 购物车
          </a>
          <a href="/portal/addresses" style={{ color: '#fff' }}>
            收货地址
          </a>
          <a href="/portal/seller" style={{ color: '#fff' }}>
            {sellerNavLabel}
          </a>
          <span>
            <UserOutlined /> {initialState?.currentUser?.name || '买家'}
          </span>
          <a href="/user/login" style={{ color: '#fff' }}>
            切换账号
          </a>
        </Space>
      </div>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: 24 }}>
        <Tabs
          items={[
            {
              key: 'products',
              label: '商品',
              children: (
                <Row gutter={[16, 16]}>
                  {(products ?? []).map((item) => (
                    <Col xs={24} sm={12} md={8} lg={6} key={item.id}>
                      <Card
                        loading={isLoading}
                        cover={
                          <div
                            style={{
                              height: 160,
                              background:
                                'linear-gradient(135deg,#e6f4ff,#bae0ff)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 48,
                              color: '#1677ff',
                            }}
                          >
                            <ShoppingCartOutlined />
                          </div>
                        }
                        actions={[
                          <Button
                            key="detail"
                            type="link"
                            onClick={() => {
                              window.location.href = `/portal/products/${item.id}`;
                            }}
                          >
                            查看详情
                          </Button>,
                          <Button
                            key="cart"
                            type="link"
                            disabled={!item.sku || item.sku.stock <= 0}
                            onClick={async () => {
                              if (!item.sku) return;
                              await addCartItem({
                                sku_id: item.sku.id,
                                quantity: 1,
                              });
                              message.success('已加入购物车');
                            }}
                          >
                            加入购物车
                          </Button>,
                          <Button
                            key="buy"
                            type="link"
                            disabled={!item.sku || item.sku.stock <= 0}
                            onClick={() => openBuy(item)}
                          >
                            立即购买
                          </Button>,
                        ]}
                      >
                        <Card.Meta
                          title={item.name}
                          description={
                            <Space orientation="vertical" size={4}>
                              <Typography.Text type="secondary">
                                {item.subtitle || '-'}
                              </Typography.Text>
                              <span
                                style={{
                                  color: '#ff4d4f',
                                  fontSize: 18,
                                  fontWeight: 600,
                                }}
                              >
                                ¥
                                {((item.sku?.price_cents ?? 0) / 100).toFixed(
                                  2,
                                )}
                              </span>
                              <Tag>卖家 {item.seller_id}</Tag>
                            </Space>
                          }
                        />
                      </Card>
                    </Col>
                  ))}
                </Row>
              ),
            },
            {
              key: 'orders',
              label: '我的订单',
              children: (
                <Card>
                  {(orders ?? []).map((item) => (
                    <div
                      key={item.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '16px 0',
                        borderBottom: '1px solid #f0f0f0',
                      }}
                    >
                      <Space orientation="vertical" size={2}>
                        <strong>{item.order_no}</strong>
                        <Typography.Text type="secondary">
                          ¥{(item.payable_amount_cents / 100).toFixed(2)}
                        </Typography.Text>
                      </Space>
                      <Space>
                        <Tag color={statusColor(item.status)}>
                          {item.status}
                        </Tag>
                        {item.status === 'pending_payment' && (
                          <Button
                            size="small"
                            type="primary"
                            onClick={async () => {
                              await mockPayPortalOrder(item.id);
                              message.success('支付成功');
                              refetchOrders();
                            }}
                          >
                            模拟支付
                          </Button>
                        )}
                        {item.status === 'shipped' && (
                          <Button
                            size="small"
                            onClick={async () => {
                              await confirmPortalOrder(item.id);
                              message.success('已确认收货');
                              refetchOrders();
                            }}
                          >
                            确认收货
                          </Button>
                        )}
                      </Space>
                    </div>
                  ))}
                </Card>
              ),
            },
          ]}
        />
      </div>

      <Modal
        title={product?.name}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={handleBuy}
        destroyOnHidden
      >
        <Form form={buyForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="数量" name="quantity" rules={[{ required: true }]}>
            <InputNumber
              min={1}
              max={product?.sku?.stock ?? 1}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item
            label="收货人"
            name="receiver_name"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="手机号"
            name="receiver_phone"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="收货地址"
            name="address"
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PortalPage;
