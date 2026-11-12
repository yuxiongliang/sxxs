import { ReloadOutlined, ShopOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { App, Button, Card, Popconfirm, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React from 'react';
import { listAdminSellers, reviewSeller } from '@/services/commerce/api';
import type { SellerRecord } from '@/services/commerce/types';
import { KYC_STATUS, labelOf, SELLER_STATUS } from '@/utils/labels';
import SettingPage from '../../system/components/SettingPage';

const statusColor = (status: string) =>
  status === 'active' ? 'success' : status === 'pending' ? 'gold' : 'default';

const SellerManagementPage: React.FC = () => {
  const { message } = App.useApp();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-sellers'],
    queryFn: listAdminSellers,
  });

  const columns: ColumnsType<SellerRecord> = [
    {
      title: '卖家',
      dataIndex: 'display_name',
      render: (_, record) => (
        <Space>
          <ShopOutlined style={{ color: '#1677ff' }} />
          <span style={{ fontWeight: 600 }}>{record.display_name}</span>
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'seller_type' },
    {
      title: 'KYC',
      dataIndex: 'kyc_status',
      render: (value: string) => (
        <Tag color={value === 'approved' ? 'success' : 'gold'}>
          {labelOf(KYC_STATUS, value)}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (value: string) => (
        <Tag color={statusColor(value)}>{labelOf(SELLER_STATUS, value)}</Tag>
      ),
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) =>
        record.status === 'pending' || record.kyc_status !== 'approved' ? (
          <Popconfirm
            title="通过卖家入驻审核？"
            onConfirm={async () => {
              await reviewSeller(record.id, {
                status: 'active',
                kyc_status: 'approved',
              });
              message.success('卖家审核通过');
              refetch();
            }}
          >
            <Button type="link" size="small">
              通过审核
            </Button>
          </Popconfirm>
        ) : record.status === 'active' ? (
          <Popconfirm
            title="确定停用该卖家？"
            onConfirm={async () => {
              await reviewSeller(record.id, {
                status: 'suspended',
                kyc_status: record.kyc_status,
              });
              message.success('卖家已停用');
              refetch();
            }}
          >
            <Button type="link" size="small" danger>
              停用
            </Button>
          </Popconfirm>
        ) : null,
    },
  ];

  return (
    <SettingPage
      title="卖家管理"
      subTitle="C2C 卖家入驻、KYC 与店铺状态"
      icon={<ShopOutlined />}
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
    </SettingPage>
  );
};

export default SellerManagementPage;
