import {
  ArrowRightOutlined,
  AuditOutlined,
  CloudServerOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link, useModel } from '@umijs/max';
import { Button, Card, Col, Row, Space, Tag, Typography } from 'antd';
import { getDashboardOverview } from '@/services/dashboard/api';

/** 平台端是独立系统（赛霄玄思 SaaS 管理平台），这里只做跨系统跳转。 */
const PLATFORM_CONSOLE_URL = 'http://localhost:8001/tenants';

const { Title, Paragraph, Text } = Typography;

const CAPABILITIES = [
  {
    icon: <SafetyCertificateOutlined />,
    title: '多租户与细粒度权限',
    desc: '全局用户 + 租户成员模型，RBAC 权限码 + 平台级作用域，跨租户数据严格隔离。',
    href: '/users/list',
  },
  {
    icon: <ShopOutlined />,
    title: 'C2C 卖家与商品',
    desc: '卖家入驻审核、商品上下架审核、SKU 与库存占用，卖家和商品都按租户隔离。',
    href: '/products',
  },
  {
    icon: <ShoppingCartOutlined />,
    title: '交易与履约',
    desc: '一次结算按卖家拆单，支付、发货、退款、确认收货全链路留痕。',
    href: '/orders',
  },
  {
    icon: <WalletOutlined />,
    title: '佣金与结算',
    desc: '佣金规则可按卖家/分类配置，账期冻结、提现审核、结算批次一路到打款。',
    href: '/finance',
  },
  {
    icon: <MessageOutlined />,
    title: 'IM 与内容审核',
    desc: 'WebSocket 实时会话、已读回执、图片消息，违规内容举报后可下架取证。',
    href: '/messages',
  },
  {
    icon: <CloudServerOutlined />,
    title: 'SaaS 计费与审计',
    desc: '套餐、订阅、账单与功能开关，关键操作全部落审计日志。',
    href: PLATFORM_CONSOLE_URL,
  },
];

const STEPS = [
  {
    title: '确认套餐',
    desc: '在「平台管理 > 租户」查看订阅状态与套餐周期。',
    href: PLATFORM_CONSOLE_URL,
  },
  {
    title: '邀请团队成员',
    desc: '用户管理里创建账号并分配角色，权限码即时生效。',
    href: '/users/list',
  },
  {
    title: '审核卖家与商品',
    desc: '卖家入驻与商品上架需要审核，通过后才可在商城售卖。',
    href: '/sellers',
  },
  {
    title: '关注经营与结算',
    desc: '经营看板看成交与待办，财务中心处理提现与结算批次。',
    href: '/dashboard/analysis',
  },
];

function StatBlock(props: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {props.label}
      </Text>
      <div style={{ fontSize: 20, fontWeight: 600, lineHeight: 1.4 }}>
        {props.value}
      </div>
      {props.hint ? (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {props.hint}
        </Text>
      ) : null}
    </div>
  );
}

export default function WelcomePage() {
  const { initialState } = useModel('@@initialState');
  const { data: overview } = useQuery({
    queryKey: ['welcome-overview'],
    queryFn: () => getDashboardOverview(7),
    retry: false,
  });

  const user = initialState?.currentUser;
  const tenant = initialState?.currentTenant;
  const usage = overview?.usage;

  return (
    <div>
      <Card
        styles={{ body: { padding: 32 } }}
        style={{
          marginBottom: 16,
          border: 'none',
          background:
            'linear-gradient(120deg, #e6f0ff 0%, #f6f9ff 45%, #ffffff 100%)',
        }}
      >
        <Space orientation="vertical" size={4}>
          <Tag color="blue">{tenant?.name ?? '演示租户'}</Tag>
          <Title level={2} style={{ margin: '8px 0 0' }}>
            {`欢迎回来，${user?.name ?? '管理员'}`}
          </Title>
          <Paragraph
            type="secondary"
            style={{ marginBottom: 8, maxWidth: 720 }}
          >
            '这是 C2C 多卖家商城的管理后台：租户与权限、卖家与商品、交易履约、IM
            客服、佣金结算、SaaS 计费与审计，全部在这里。'
          </Paragraph>
        </Space>
        <Space wrap>
          <Button type="primary" href="/dashboard/analysis">
            进入经营看板
            <ArrowRightOutlined />
          </Button>
          <Button href="/portal" target="_blank">
            打开买家商城
          </Button>
          <Button href="/dashboard/workplace">我的工作台</Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card title="平台能力" size="small">
            <Row gutter={[16, 16]}>
              {CAPABILITIES.map((item) => (
                <Col xs={24} md={12} key={item.title}>
                  <Link to={item.href}>
                    <Card
                      size="small"
                      hoverable
                      styles={{ body: { padding: 16 } }}
                    >
                      <Space align="start">
                        <span style={{ fontSize: 18, color: '#1677ff' }}>
                          {item.icon}
                        </span>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: 2 }}>
                            {item.title}
                          </div>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {item.desc}
                          </Text>
                        </div>
                      </Space>
                    </Card>
                  </Link>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card title="套餐详情" size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[8, 16]}>
              <Col span={12}>
                <StatBlock
                  label="套餐"
                  value={usage?.plan_name ?? usage?.plan ?? '—'}
                  hint={
                    usage?.subscription_status
                      ? `状态 ${usage.subscription_status}`
                      : undefined
                  }
                />
              </Col>
              <Col span={12}>
                <StatBlock
                  label="订阅剩余"
                  value={
                    usage?.days_left === null || usage?.days_left === undefined
                      ? '—'
                      : `${usage.days_left} 天`
                  }
                />
              </Col>
            </Row>
          </Card>

          <Card title="快捷操作" size="small">
            <Space orientation="vertical" style={{ width: '100%' }} size={10}>
              <Link to="/orders">
                <ShoppingCartOutlined /> {'订单管理'}
              </Link>
              <Link to="/products">
                <ShopOutlined /> {'商品管理'}
              </Link>
              <Link to="/finance">
                <WalletOutlined /> {'财务结算'}
              </Link>
              <Link to="/system/audit">
                <AuditOutlined /> {'审计日志'}
              </Link>
              <Link to="/docs" target="_blank">
                <ThunderboltOutlined /> {'接口文档 /docs'}
              </Link>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="快速开始" size="small" style={{ marginTop: 16 }}>
        <Row gutter={[16, 16]}>
          {STEPS.map((step, index) => (
            <Col xs={24} md={12} xl={6} key={step.title}>
              <Link to={step.href}>
                <Card size="small" hoverable styles={{ body: { padding: 16 } }}>
                  <Tag color="blue">{`第 ${index + 1} 步`}</Tag>
                  <div style={{ fontWeight: 600, margin: '8px 0 2px' }}>
                    {step.title}
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {step.desc}
                  </Text>
                </Card>
              </Link>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
}
