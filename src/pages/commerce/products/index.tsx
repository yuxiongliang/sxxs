import {
  EditOutlined,
  ReloadOutlined,
  ShoppingOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import AttachmentUpload from '@/components/AttachmentUpload';
import {
  listAdminProducts,
  reviewProduct,
  updateAdminProduct,
} from '@/services/commerce/api';
import type { ProductRecord } from '@/services/commerce/types';
import SettingPage from '../../system/components/SettingPage';

const statusColor = (status: string) =>
  status === 'on_sale'
    ? 'success'
    : status === 'pending_review'
      ? 'gold'
      : 'default';

const ProductManagementPage: React.FC = () => {
  const { message } = App.useApp();
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<ProductRecord>();
  const [form] = Form.useForm();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-products'],
    queryFn: listAdminProducts,
  });

  const openEdit = (record: ProductRecord) => {
    setEditing(record);
    form.setFieldsValue(record);
    setEditOpen(true);
  };

  const handleSave = async () => {
    if (!editing) return;
    const values = await form.validateFields();
    await updateAdminProduct(editing.id, values);
    message.success('商品已更新');
    setEditOpen(false);
    refetch();
  };

  const columns: ColumnsType<ProductRecord> = [
    {
      title: '商品',
      dataIndex: 'name',
      render: (_, record) => (
        <Space>
          <ShoppingOutlined style={{ color: '#1677ff' }} />
          <div>
            <div style={{ fontWeight: 600 }}>{record.name}</div>
            <div style={{ color: '#8c8c8c', fontSize: 12 }}>
              {record.subtitle || '-'}
            </div>
          </div>
        </Space>
      ),
    },
    { title: '卖家 ID', dataIndex: 'seller_id', width: 100 },
    { title: '店铺 ID', dataIndex: 'shop_id', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 140,
      render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag>,
    },
    {
      title: '操作',
      width: 260,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          {record.status === 'on_sale' ? (
            <Popconfirm
              title="确定下架该商品？"
              onConfirm={async () => {
                await reviewProduct(record.id, { status: 'off_sale' });
                message.success('商品已下架');
                refetch();
              }}
            >
              <Button type="link" size="small" danger>
                下架
              </Button>
            </Popconfirm>
          ) : (
            <Popconfirm
              title="审核通过并上架？"
              onConfirm={async () => {
                await reviewProduct(record.id, { status: 'on_sale' });
                message.success('商品已上架');
                refetch();
              }}
            >
              <Button type="link" size="small">
                通过上架
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <SettingPage
      title="商品管理"
      subTitle="C2C 商品审核与在售状态"
      icon={<ShoppingOutlined />}
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

      <Modal
        title="编辑商品"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleSave}
        destroyOnHidden
        width={560}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
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
          <Form.Item label="主图 URL" name="main_image">
            <Input placeholder="上传后自动填入" />
          </Form.Item>
          <Form.Item label="上传主图">
            <AttachmentUpload
              sourceModule="product"
              accept="image/*"
              multiple={false}
              onUploaded={(record) =>
                form.setFieldValue('main_image', record.url)
              }
            />
          </Form.Item>
        </Form>
      </Modal>
    </SettingPage>
  );
};

export default ProductManagementPage;
