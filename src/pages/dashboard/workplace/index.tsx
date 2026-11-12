import {
  CheckCircleOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  WalletOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link, useAccess, useModel } from '@umijs/max';
import {
  Alert,
  Card,
  Col,
  Empty,
  Row,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import { formatCents, statusLabel } from '@/pages/dashboard/analysis/format';
import { listAdminOrders } from '@/services/commerce/api';
import { getDashboardOverview } from '@/services/dashboard/api';

const { Text, Title } = Typography;

const STATUS_COLORS: Record<string, string> = {
  pending_payment: 'orange',
  paid: 'blue',
  shipped: 'geekblue',
  completed: 'green',
  cancelled: 'default',
  refunded: 'red',
};

function TodoCard(props: {
  icon: React.ReactNode;
  title: string;
  count: number;
  href: string;
  hint?: string;
}) {
  const empty = props.count === 0;
  return (
    <Link to={props.href}>
      <Card size="small" hoverable styles={{ body: { padding: 16 } }}>
        <Space align="center" size={12}>
          <span
            style={{
              fontSize: 20,
              color: empty ? '#bfbfbf' : '#1677ff',
              display: 'inline-flex',
            }}
          >
            {props.icon}
          </span>
          <div>
            <div style={{ fontSize: 22, fontWeight: 600, lineHeight: 1.3 }}>
              {props.count}
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {props.title}
            </Text>
          </div>
        </Space>
        {props.hint ? (
          <div style={{ marginTop: 8 }}>
            <Text
              type={empty ? 'secondary' : 'danger'}
              style={{ fontSize: 12 }}
            >
              {props.hint}
            </Text>
          </div>
        ) : null}
      </Card>
    </Link>
  );
}

export default function WorkplacePage() {
  const access = useAccess();
  const { initialState } = useModel('@@initialState');
  const user = initialState?.currentUser;
  const tenant = initialState?.currentTenant;

  const overviewQuery = useQuery({
    queryKey: ['workplace-overview'],
    queryFn: () => getDashboardOverview(7),
    retry: false,
  });
  const ordersQuery = useQuery({
    queryKey: ['workplace-orders'],
    queryFn: () => listAdminOrders(),
    retry: false,
  });

  const kpi = overviewQuery.data?.kpi;
  const usage = overviewQuery.data?.usage;
  const canReadOrders = access.canOrderReadTenant;

  const todos = [
    {
      icon: <ShoppingCartOutlined />,
      title: '待支付订单',
      count: kpi?.pending_payment_orders ?? 0,
      href: '/orders',
      visible: canReadOrders,
    },
    {
      icon: <CheckCircleOutlined />,
      title: '待审商品',
      count: kpi?.products_pending_review ?? 0,
      href: '/products',
      visible: access.canProductManage,
    },
    {
      icon: <ShopOutlined />,
      title: '待审卖家',
      count: kpi?.sellers_pending ?? 0,
      href: '/sellers',
      visible: access.canSellerRead,
    },
    {
      icon: <WalletOutlined />,
      title: '待审提现',
      count: kpi?.payouts_pending_count ?? 0,
      href: '/finance',
      hint: kpi ? `合计 ${formatCents(kpi.payouts_pending_cents)}` : undefined,
      visible: access.canPayoutRead,
    },
    {
      icon: <WarningOutlined />,
      title: '待处理举报',
      count: kpi?.im_reports_open ?? 0,
      href: '/messages',
      visible: access.canImRead,
    },
  ].filter((item) => item.visible);

  const recentOrders = (ordersQuery.data ?? []).slice(0, 6);
  const columns = [
    {
      title: '订单号',
      dataIndex: 'order_no',
      ellipsis: true,
      render: (value: string, _record: { id: number }) => (
        <Link to="/orders">{value}</Link>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: string) => (
        <Tag color={STATUS_COLORS[value] ?? 'default'}>
          {statusLabel(value)}
        </Tag>
      ),
    },
    {
      title: '金额',
      dataIndex: 'payable_amount_cents',
      width: 120,
      align: 'right' as const,
      render: (value: number) => formatCents(value),
    },
  ];

  const today = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });

  return (
    <div>
      <Card styles={{ body: { padding: 24 } }} style={{ marginBottom: 16 }}>
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col>
            <Title level={4} style={{ margin: 0 }}>
              {`你好，${user?.name ?? '管理员'}`}
            </Title>
            <Space size={8} style={{ marginTop: 6 }} wrap>
              <Text type="secondary">{today}</Text>
              <Tag color="blue">{tenant?.name ?? '演示租户'}</Tag>
              {usage?.plan_name ? <Tag>{usage.plan_name}</Tag> : null}
            </Space>
          </Col>
          <Col>
            <Link to="/dashboard/analysis">查看经营看板 →</Link>
          </Col>
        </Row>
      </Card>

      {usage?.subscription_status === 'past_due' ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          title="当前订阅已欠费，宽限期结束后会自动降级到免费套餐"
        />
      ) : null}

      <Card title="我的待办" size="small" style={{ marginBottom: 16 }}>
        {overviewQuery.isLoading ? (
          <Skeleton active paragraph={{ rows: 2 }} />
        ) : todos.length ? (
          <Row gutter={[16, 16]}>
            {todos.map((item) => (
              <Col
                xs={24}
                sm={12}
                xl={Math.max(4, Math.floor(24 / todos.length))}
                key={item.title}
              >
                <TodoCard
                  icon={item.icon}
                  title={item.title}
                  count={item.count}
                  href={item.href}
                  hint={item.hint}
                />
              </Col>
            ))}
          </Row>
        ) : (
          <Empty description="当前账号没有需要处理的待办" />
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card
            title="最近订单"
            size="small"
            extra={<Link to="/orders">全部订单</Link>}
          >
            {ordersQuery.isError ? (
              <Alert
                type="error"
                showIcon
                title="订单加载失败（可能需要订单查看权限）"
              />
            ) : (
              <Table
                rowKey="id"
                size="small"
                columns={columns}
                dataSource={recentOrders}
                loading={ordersQuery.isLoading}
                pagination={false}
                locale={{ emptyText: <Empty description="还没有订单" /> }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="快捷入口" size="small">
            <Space orientation="vertical" size={10} style={{ width: '100%' }}>
              {access.canUserRead ? (
                <Link to="/users/list">用户与成员</Link>
              ) : null}
              {access.canProductRead ? (
                <Link to="/products">商品管理</Link>
              ) : null}
              {canReadOrders ? <Link to="/orders">订单管理</Link> : null}
              {access.canSellerRead ? (
                <Link to="/sellers">卖家管理</Link>
              ) : null}
              {access.canPayoutRead ? (
                <Link to="/finance">财务结算</Link>
              ) : null}
              {access.canImRead ? <Link to="/messages">消息中心</Link> : null}
              {access.canAuditRead ? (
                <Link to="/system/audit">审计日志</Link>
              ) : null}
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
