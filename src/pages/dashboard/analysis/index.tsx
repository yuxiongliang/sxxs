import { Column, Pie } from '@ant-design/plots';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Skeleton,
  Statistic,
  Table,
  Tag,
} from 'antd';
import type { ReactNode } from 'react';
import { useState } from 'react';
import type { DashboardTopProduct } from '@/services/dashboard/api';
import { getDashboardOverview } from '@/services/dashboard/api';
import { formatCents, percentChange, shortDay, statusLabel } from './format';

const RANGE_OPTIONS = [
  { label: '近 7 天', value: 7 },
  { label: '近 14 天', value: 14 },
  { label: '近 30 天', value: 30 },
];

function Delta({ current, previous }: { current: number; previous: number }) {
  const change = percentChange(current, previous);
  if (change === null) {
    return <span style={{ color: '#999', fontSize: 12 }}>较昨日 —</span>;
  }
  const up = change >= 0;
  return (
    <span style={{ color: up ? '#3f8600' : '#cf1322', fontSize: 12 }}>
      {'较昨日 '}
      {up ? '+' : ''}
      {change}
      {'%'}
    </span>
  );
}

function KpiCard(props: {
  title: string;
  value: number | string;
  hint?: ReactNode;
  suffix?: string;
}) {
  return (
    <Card size="small" styles={{ body: { padding: 16 } }}>
      <Statistic
        title={props.title}
        value={props.value}
        suffix={props.suffix}
      />
      {props.hint ? (
        <div style={{ marginTop: 4, color: '#999', fontSize: 12 }}>
          {props.hint}
        </div>
      ) : null}
    </Card>
  );
}

export default function AnalysisPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-overview', days],
    queryFn: () => getDashboardOverview(days),
  });

  if (isError) {
    return (
      <Alert
        type="error"
        showIcon
        title="经营数据加载失败"
        description={String((error as Error)?.message ?? '未知错误')}
        action={
          <Button size="small" onClick={() => refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  if (isLoading || !data) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  const { kpi, trend, order_status, top_products, usage, range, totals } = data;

  const gmvSeries = trend.map((point) => ({
    x: shortDay(point.date),
    y: Number((point.gmv_cents / 100).toFixed(2)),
  }));
  const statusSeries = order_status.map((bucket) => ({
    x: statusLabel(bucket.status),
    y: bucket.count,
  }));

  const topColumns = [
    { title: '商品', dataIndex: 'name', ellipsis: true },
    {
      title: '件数',
      dataIndex: 'quantity',
      width: 90,
      align: 'right' as const,
    },
    {
      title: '销售额',
      dataIndex: 'gmv_cents',
      width: 130,
      align: 'right' as const,
      render: (value: number) => formatCents(value),
    },
  ];

  return (
    <div>
      {usage.subscription_status === 'past_due' ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          title="当前订阅已欠费"
          description="账单已逾期，宽限期结束后将自动降级到免费套餐。请尽快在「平台管理 > 租户」完成续费。"
        />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="今日成交额"
            value={formatCents(kpi.gmv_today_cents)}
            hint={
              <Delta
                current={kpi.gmv_today_cents}
                previous={kpi.gmv_yesterday_cents}
              />
            }
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="今日订单"
            value={kpi.orders_today}
            suffix="单"
            hint={
              <Delta
                current={kpi.orders_today}
                previous={kpi.orders_yesterday}
              />
            }
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="今日新增买家"
            value={kpi.new_buyers_today}
            suffix="人"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="待支付订单"
            value={kpi.pending_payment_orders}
            suffix="单"
            hint="含历史未支付"
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="在售商品"
            value={kpi.products_on_sale}
            suffix="个"
            hint={`待审核 ${kpi.products_pending_review} 个`}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="活跃卖家"
            value={kpi.sellers_active}
            suffix="家"
            hint={`待审核 ${kpi.sellers_pending} 家`}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard
            title="待审提现"
            value={kpi.payouts_pending_count}
            suffix="笔"
            hint={formatCents(kpi.payouts_pending_cents)}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard title="待处理举报" value={kpi.im_reports_open} suffix="条" />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} xl={16}>
          <Card
            title="成交趋势"
            extra={
              <Segmented
                value={days}
                onChange={(value) => setDays(Number(value))}
                options={RANGE_OPTIONS}
              />
            }
          >
            <div style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
              {'数据区间 ' +
                range.start +
                ' ~ ' +
                range.end +
                '（' +
                range.timezone +
                '）· 区间累计 ' +
                formatCents(totals.gmv_cents)}
            </div>
            {gmvSeries.length ? (
              <Column
                height={300}
                data={gmvSeries}
                xField="x"
                yField="y"
                paddingBottom={12}
                axis={{ x: { title: false }, y: { title: false } }}
                scale={{ x: { paddingInner: 0.4 } }}
                tooltip={{ name: '成交额（元）', channel: 'y' }}
              />
            ) : (
              <Empty description="区间内暂无成交" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="订单状态分布">
            {statusSeries.length ? (
              <Pie
                height={300}
                radius={0.8}
                innerRadius={0.5}
                angleField="y"
                colorField="x"
                data={statusSeries}
                legend={false}
                label={{
                  position: 'spider',
                  text: (item: { x: string; y: number }) =>
                    `${item.x}: ${item.y}`,
                }}
              />
            ) : (
              <Empty description="暂无订单" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} xl={14}>
          <Card
            title={`热销商品 Top ${top_products.length || 5}`}
            extra={
              <span style={{ color: '#999', fontSize: 12 }}>
                {`近 ${days} 天`}
              </span>
            }
          >
            <Table<DashboardTopProduct>
              rowKey="product_id"
              size="small"
              columns={topColumns}
              dataSource={top_products}
              pagination={false}
              locale={{ emptyText: <Empty description="区间内暂无成交商品" /> }}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card
            title="套餐详情"
            extra={
              <Tag color="blue">
                {usage.plan_name ?? usage.plan ?? '未订阅'}
              </Tag>
            }
          >
            <div style={{ display: 'flex', gap: 40 }}>
              <div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>订阅状态</div>
                <div style={{ fontSize: 20, fontWeight: 600 }}>
                  {usage.subscription_status ?? '—'}
                </div>
              </div>
              <div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>剩余天数</div>
                <div style={{ fontSize: 20, fontWeight: 600 }}>
                  {usage.days_left === null || usage.days_left === undefined
                    ? '—'
                    : `${usage.days_left} 天`}
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
