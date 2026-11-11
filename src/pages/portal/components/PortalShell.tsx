import {
  HomeOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link, useModel } from '@umijs/max';
import { Badge, Space } from 'antd';
import React from 'react';
import { getSellerApplication } from '@/services/commerce/api';

interface PortalShellProps {
  children: React.ReactNode;
  title?: string;
  cartCount?: number;
  maxWidth?: number;
}

/**
 * Shared chrome for the standalone C-end portal pages.
 *
 * Portal pages are declared with `layout: false` in `config/routes.ts`, so they
 * must render their own header instead of relying on ProLayout.
 */
const PortalShell: React.FC<PortalShellProps> = ({
  children,
  title,
  cartCount = 0,
  maxWidth = 1280,
}) => {
  const { initialState } = useModel('@@initialState');
  // 开店状态决定导航文案：未开店引导申请、审核中打标、通过后直接进店管理
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Link
            to="/portal"
            style={{ color: '#fff', fontSize: 24, fontWeight: 700 }}
          >
            <ShopOutlined /> C2C 商城
          </Link>
          {title ? <span style={{ opacity: 0.85 }}>/ {title}</span> : null}
        </div>
        <Space size={20}>
          <Link to="/portal" style={{ color: '#fff' }}>
            <HomeOutlined /> 商城首页
          </Link>
          <Link to="/portal/cart" style={{ color: '#fff' }}>
            <Badge count={cartCount} size="small" offset={[6, -2]}>
              <ShoppingCartOutlined style={{ color: '#fff' }} /> 购物车
            </Badge>
          </Link>
          <Link to="/portal/addresses" style={{ color: '#fff' }}>
            收货地址
          </Link>
          {/* 买家与店主同一个入口：没开店引导申请，审核中打标，通过后直接管理 */}
          <Link to="/portal/seller" style={{ color: '#fff' }}>
            <ShopOutlined style={{ color: '#fff' }} /> {sellerNavLabel}
          </Link>
          <span>
            <UserOutlined /> {initialState?.currentUser?.name || '买家'}
          </span>
        </Space>
      </div>
      <div style={{ maxWidth, margin: '0 auto', padding: 24 }}>{children}</div>
    </div>
  );
};

export default PortalShell;
