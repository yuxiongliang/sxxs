import {
  ProfileOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons';
import { Card, Col, Row, Typography } from 'antd';
import PortalShell from './components/PortalShell';

const { Text } = Typography;

/**
 * 买家个人中心首页。
 *
 * 按需求：这里只做「个人中心 + 卖家管理」的入口聚合，**不再提供商品浏览入口**；
 * 逛商品与商品详情已迁到站点前台 /products。
 */
const ENTRIES = [
  {
    key: 'orders',
    title: '我的订单',
    desc: '查看订单状态、支付与确认收货',
    href: '/portal/orders',
    icon: <ProfileOutlined />,
  },
  {
    key: 'cart',
    title: '购物车',
    desc: '结算已挑选的商品',
    href: '/portal/cart',
    icon: <ShoppingCartOutlined />,
  },
  {
    key: 'addresses',
    title: '收货地址',
    desc: '管理常用收货地址',
    href: '/portal/addresses',
    icon: <EnvironmentOutlined />,
  },
  {
    key: 'seller',
    title: '卖家中心',
    desc: '店铺、商品、订单与结算',
    href: '/portal/seller',
    icon: <ShopOutlined />,
  },
];

export default function PortalCenterPage() {
  return (
    <PortalShell title="个人中心">
      <Row gutter={[16, 16]}>
        {ENTRIES.map((entry) => (
          <Col xs={24} sm={12} xl={6} key={entry.key}>
            <a href={entry.href}>
              <Card hoverable styles={{ body: { padding: 20 } }}>
                <div
                  style={{
                    fontSize: 24,
                    color: 'var(--ant-color-primary)',
                    marginBottom: 8,
                  }}
                >
                  {entry.icon}
                </div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {entry.title}
                </div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {entry.desc}
                </Text>
              </Card>
            </a>
          </Col>
        ))}
      </Row>
    </PortalShell>
  );
}
