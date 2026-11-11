import { PlusOutlined, ShopOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import PortalShell from '@/pages/portal/components/PortalShell';
import {
  applySeller,
  createSellerProduct,
  getSellerApplication,
  getSellerProfile,
  listSellerOrders,
  listSellerProducts,
  requestSellerPayout,
  shipMySellerOrder,
} from '@/services/commerce/api';
import type {
  SellerOrderRecord,
  SellerProductRecord,
} from '@/services/commerce/types';

const SellerPage: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [productOpen, setProductOpen] = useState(false);
  const [shipOpen, setShipOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<SellerOrderRecord>();
  const applicationQuery = useQuery({
    queryKey: ['seller-application'],
    queryFn: getSellerApplication,
    retry: false,
  });
  const application = applicationQuery.data;
  const [shopName, setShopName] = useState('');
  const [applying, setApplying] = useState(false);

  const handleApply = async () => {
    if (shopName.trim().length < 2) {
      message.error('店铺名至少 2 个字');
      return;
    }
    setApplying(true);
    try {
      await applySeller({ shop_name: shopName.trim() });
      message.success('申请已提交，等待平台审核');
      await queryClient.invalidateQueries({ queryKey: ['seller-application'] });
    } catch (error: any) {
      message.error(error?.message || '申请失败');
    } finally {
      setApplying(false);
    }
  };
  const [productForm] = Form.useForm();
  const [shipForm] = Form.useForm();

  const { data: profile } = useQuery({
    queryKey: ['seller-profile'],
    queryFn: getSellerProfile,
  });
  const { data: products, isLoading: productsLoading } = useQuery({
    queryKey: ['seller-products'],
    queryFn: listSellerProducts,
  });
  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ['seller-orders'],
    queryFn: listSellerOrders,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['seller-products'] });
    queryClient.invalidateQueries({ queryKey: ['seller-orders'] });
    queryClient.invalidateQueries({ queryKey: ['seller-profile'] });
  };

  const handleCreateProduct = async () => {
    const values = await productForm.validateFields();
    await createSellerProduct({
      name: values.name,
      subtitle: values.subtitle,
      price_cents: Math.round(values.price * 100),
      stock: values.stock,
    });
    message.success('商品已提交审核');
    setProductOpen(false);
    productForm.resetFields();
    refresh();
  };

  const handleShip = async () => {
    if (!selectedOrder) return;
    const values = await shipForm.validateFields();
    await shipMySellerOrder(selectedOrder.id, values);
    message.success('发货成功');
    setShipOpen(false);
    shipForm.resetFields();
    refresh();
  };

  const handlePayout = async () => {
    try {
      const payout = await requestSellerPayout();
      message.success(`结算成功：¥${(payout.amount_cents / 100).toFixed(2)}`);
      refresh();
    } catch (error: any) {
      message.error(error?.message || '结算失败');
    }
  };

  const productColumns: ColumnsType<SellerProductRecord> = [
    { title: '商品', dataIndex: 'name' },
    {
      title: '状态',
      dataIndex: 'status',
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '价格',
      dataIndex: 'price_cents',
      render: (v: number) => `¥${(v / 100).toFixed(2)}`,
    },
    { title: '库存', dataIndex: 'stock' },
  ];

  const orderColumns: ColumnsType<SellerOrderRecord> = [
    { title: '卖家单号', dataIndex: 'seller_order_no' },
    {
      title: '状态',
      dataIndex: 'status',
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '商品金额',
      dataIndex: 'goods_amount_cents',
      render: (v: number) => `¥${(v / 100).toFixed(2)}`,
    },
    {
      title: '佣金',
      dataIndex: 'commission_amount_cents',
      render: (v: number) => `¥${(v / 100).toFixed(2)}`,
    },
    {
      title: '应结算',
      dataIndex: 'payable_to_seller_cents',
      render: (v: number) => `¥${(v / 100).toFixed(2)}`,
    },
    {
      title: '操作',
      width: 120,
      render: (_, record) =>
        ['paid', 'processing'].includes(record.status) ? (
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSelectedOrder(record);
              setShipOpen(true);
            }}
          >
            发货
          </Button>
        ) : null,
    },
  ];

  if (applicationQuery.isLoading) {
    return (
      <PortalShell>
        <div style={{ maxWidth: 720, margin: '0 auto', padding: 48 }}>
          加载中…
        </div>
      </PortalShell>
    );
  }

  if (!application?.has_seller) {
    return (
      <PortalShell>
        <div style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
          <Card title="申请成为店主">
            <Space orientation="vertical" size={12} style={{ width: '100%' }}>
              <Typography.Text type="secondary">
                你目前是买家。开一家自己的店即可在同一套页面里管理商品、订单与结算，无需切换入口。
              </Typography.Text>
              <Input
                placeholder="店铺名称（例如：阿强的二手键盘铺）"
                value={shopName}
                onChange={(event) => setShopName(event.target.value)}
                maxLength={64}
              />
              <Button type="primary" loading={applying} onClick={handleApply}>
                提交开店申请
              </Button>
            </Space>
          </Card>
        </div>
      </PortalShell>
    );
  }

  if (application.status === 'pending') {
    return (
      <PortalShell>
        <div style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
          <Alert
            type="info"
            showIcon
            title="开店申请审核中"
            description="平台审核通过后，这里会变成你的店铺管理页（商品 / 订单 / 结算）。"
          />
        </div>
      </PortalShell>
    );
  }

  return (
    <PortalShell>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
        <Card style={{ marginBottom: 16 }}>
          <Space
            orientation="vertical"
            size={4}
            style={{ width: '100%', justifyContent: 'space-between' }}
          >
            <div>
              <Typography.Title level={4} style={{ margin: 0 }}>
                <ShopOutlined /> {profile?.display_name || '卖家'}
              </Typography.Title>
              <Typography.Text type="secondary">
                店铺：{profile?.shop?.name || '-'} · KYC：
                {profile?.kyc_status || '-'} · 状态：{profile?.status || '-'}
              </Typography.Text>
            </div>
            <Button onClick={handlePayout}>申请结算</Button>
          </Space>
        </Card>
        <Card>
          <Tabs
            items={[
              {
                key: 'products',
                label: '我的商品',
                children: (
                  <>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      style={{ marginBottom: 16 }}
                      onClick={() => setProductOpen(true)}
                    >
                      新增商品
                    </Button>
                    <Table
                      rowKey="id"
                      loading={productsLoading}
                      columns={productColumns}
                      dataSource={products ?? []}
                      pagination={false}
                    />
                  </>
                ),
              },
              {
                key: 'orders',
                label: '我的订单',
                children: (
                  <Table
                    rowKey="id"
                    loading={ordersLoading}
                    columns={orderColumns}
                    dataSource={orders ?? []}
                    pagination={false}
                  />
                ),
              },
            ]}
          />
        </Card>

        <Modal
          title="新增商品"
          open={productOpen}
          onCancel={() => setProductOpen(false)}
          onOk={handleCreateProduct}
          destroyOnHidden
        >
          <Form form={productForm} layout="vertical" style={{ marginTop: 16 }}>
            <Form.Item
              label="商品名称"
              name="name"
              rules={[{ required: true, message: '请输入商品名称' }]}
            >
              <Input />
            </Form.Item>
            <Form.Item label="副标题" name="subtitle">
              <Input />
            </Form.Item>
            <Form.Item
              label="价格（元）"
              name="price"
              rules={[{ required: true, message: '请输入价格' }]}
            >
              <InputNumber min={0.01} precision={2} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              label="库存"
              name="stock"
              rules={[{ required: true, message: '请输入库存' }]}
            >
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </Form>
        </Modal>

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
              <Input />
            </Form.Item>
            <Form.Item
              label="运单号"
              name="tracking_no"
              rules={[{ required: true, message: '请输入运单号' }]}
            >
              <Input />
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </PortalShell>
  );
};

export default SellerPage;
