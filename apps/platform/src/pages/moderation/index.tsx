import { ReloadOutlined, SafetyOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Col,
  Empty,
  Image,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import PageShell from '@/components/PageShell';
import type { ModerationLogEntry, PlatformAttachment } from '@/services/api';
import {
  moderationDownloadUrl,
  moderationLogs,
  moderationQueue,
  moderationRestore,
  moderationReview,
  moderationStats,
  moderationTakedown,
} from '@/services/api';
import { tokens } from '@/services/http';

const REJECT_CATEGORIES = [
  { value: 'porn', label: '涉黄' },
  { value: 'violence', label: '暴力' },
  { value: 'ad_qr', label: '引流二维码' },
  { value: 'watermark', label: '违规水印' },
  { value: 'other', label: '其他违规' },
];

const STATUS_COLOR: Record<string, string> = {
  pending: 'gold',
  approved: 'green',
  rejected: 'red',
  manual: 'blue',
  failed: 'volcano',
};

const STATUS_LABEL: Record<string, string> = {
  pending: '待审',
  approved: '已通过',
  rejected: '已驳回',
  manual: '待人工',
  failed: '审核异常',
};

/**
 * 带鉴权的图片预览。
 *
 * 审核接口要求平台 token，而 <img src> 发不了 Authorization 头，
 * 所以这里用 fetch 取 blob 再转 object URL；卸载时必须 revoke，否则内存泄漏。
 */
function AuthImage({ id, size = 56 }: { id: number; size?: number }) {
  const [src, setSrc] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;

    const load = async () => {
      try {
        const response = await fetch(moderationDownloadUrl(id), {
          headers: { Authorization: `Bearer ${tokens.get() ?? ''}` },
          credentials: 'include',
        });
        if (!response.ok) return;
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setSrc(objectUrl);
      } catch {
        /* 预览失败不影响审核流程 */
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  return (
    <Image
      src={src}
      width={size}
      height={size}
      style={{ objectFit: 'cover', borderRadius: 6 }}
      placeholder
    />
  );
}

export default function ModerationPage() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const [status, setStatus] = useState('pending');
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [tenantId, setTenantId] = useState<number>();
  const [sourceRole, setSourceRole] = useState<string>();

  const [reviewTarget, setReviewTarget] = useState<PlatformAttachment>();
  const [reviewDecision, setReviewDecision] = useState<'approved' | 'rejected'>('approved');
  const [rejectCategories, setRejectCategories] = useState<string[]>([]);
  const [logsTarget, setLogsTarget] = useState<PlatformAttachment>();

  const stats = useQuery({
    queryKey: ['moderation-stats'],
    queryFn: moderationStats,
  });

  const queue = useQuery({
    queryKey: ['moderation', status, page, keyword, tenantId, sourceRole],
    queryFn: () =>
      moderationQueue({
        review_status: status === 'takedown' ? 'all' : status,
        only_takedown: status === 'takedown',
        current: page,
        pageSize: 10,
        keyword: keyword || undefined,
        tenant_id: tenantId,
        source_role: sourceRole,
      }),
  });

  const logs = useQuery({
    queryKey: ['moderation-logs', logsTarget?.id],
    queryFn: () => moderationLogs(logsTarget?.id as number),
    enabled: Boolean(logsTarget?.id),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['moderation'] });
    queryClient.invalidateQueries({ queryKey: ['moderation-stats'] });
  };

  const submitReview = useMutation({
    mutationFn: () =>
      moderationReview(
        reviewTarget?.id as number,
        reviewDecision,
        reviewDecision === 'rejected' ? rejectCategories : undefined,
      ),
    onSuccess: () => {
      message.success('审核结论已保存');
      setReviewTarget(undefined);
      setRejectCategories([]);
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const toggleTakedown = useMutation({
    mutationFn: (record: PlatformAttachment) =>
      record.admin_hidden ? moderationRestore(record.id) : moderationTakedown(record.id),
    onSuccess: () => {
      message.success('操作成功');
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const columns: ColumnsType<PlatformAttachment> = useMemo(
    () => [
      {
        title: '预览',
        width: 80,
        render: (_, record) => <AuthImage id={record.id} />,
      },
      {
        title: '文件',
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text ellipsis style={{ maxWidth: 220 }}>
              {record.original_name}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {record.mime_type} · {(record.size / 1024).toFixed(0)}KB · {record.source_module}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: '租户',
        width: 150,
        render: (_, record) => (
          <Typography.Text>{record.tenant_name ?? `#${record.tenant_id}`}</Typography.Text>
        ),
      },
      {
        title: '上传者',
        width: 140,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{record.uploader}</Typography.Text>
            <Tag>{record.uploader_role}</Tag>
          </Space>
        ),
      },
      {
        title: '可见范围',
        dataIndex: 'visibility',
        width: 100,
        render: (value: string) => <Tag color="geekblue">{value}</Tag>,
      },
      {
        title: '审核状态',
        width: 150,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Tag color={STATUS_COLOR[record.review_status] ?? 'default'}>
              {STATUS_LABEL[record.review_status] ?? record.review_status}
            </Tag>
            {record.reject_reason ? (
              <Typography.Text type="danger" style={{ fontSize: 12 }}>
                {record.reject_reason}
              </Typography.Text>
            ) : null}
            {record.admin_hidden ? <Tag color="red">已下架</Tag> : null}
          </Space>
        ),
      },
      {
        title: '时间',
        dataIndex: 'created_at',
        width: 170,
        render: (value: string) => new Date(value).toLocaleString('zh-CN'),
      },
      {
        title: '操作',
        width: 230,
        render: (_, record) => (
          <Space size={2} wrap>
            <Button
              type="link"
              size="small"
              onClick={() => {
                setReviewTarget(record);
                setReviewDecision('approved');
                setRejectCategories([]);
              }}
            >
              复核
            </Button>
            <Button
              type="link"
              size="small"
              danger={!record.admin_hidden}
              loading={toggleTakedown.isPending}
              onClick={() => toggleTakedown.mutate(record)}
            >
              {record.admin_hidden ? '解除下架' : '强制下架'}
            </Button>
            <Button type="link" size="small" onClick={() => setLogsTarget(record)}>
              日志
            </Button>
          </Space>
        ),
      },
    ],
    [toggleTakedown],
  );

  const data = stats.data;

  return (
    <PageShell
      title="内容审核"
      subTitle="全站附件审核：平台只出结论与下架，日常管理归租户"
    >
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        {[
          ['待审', data?.pending],
          ['待人工', data?.manual],
          ['审核异常', data?.failed],
          ['已驳回', data?.rejected],
          ['已通过', data?.approved],
          ['已下架', data?.takedown],
        ].map(([label, value]) => (
          <Col key={String(label)} xs={12} md={4}>
            <Card size="small">
              <Statistic title={String(label)} value={Number(value ?? 0)} />
            </Card>
          </Col>
        ))}
      </Row>

      <Card>
        <Space wrap style={{ marginBottom: 12 }}>
          <Input
            allowClear
            placeholder="文件名 / 模块"
            style={{ width: 200 }}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
          />
          <InputNumber
            placeholder="租户 ID"
            style={{ width: 120 }}
            onChange={(value) => {
              // InputNumber 的 onChange 可能是 string（清空/输入中）
              setTenantId(typeof value === 'number' ? value : undefined);
              setPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="上传者角色"
            style={{ width: 140 }}
            options={[
              { value: 'admin', label: '管理员' },
              { value: 'seller', label: '卖家' },
              { value: 'buyer', label: '买家' },
            ]}
            onChange={(value) => {
              setSourceRole(value);
              setPage(1);
            }}
          />
          <Button icon={<ReloadOutlined />} onClick={refresh}>
            刷新
          </Button>
        </Space>

        <Tabs
          activeKey={status}
          onChange={(key) => {
            setStatus(key);
            setPage(1);
          }}
          items={[
            { key: 'pending', label: '待审队列' },
            { key: 'manual', label: '人工复核' },
            { key: 'failed', label: '审核异常' },
            { key: 'rejected', label: '已驳回' },
            { key: 'takedown', label: '已下架' },
          ]}
        />

        <Table
          rowKey="id"
          loading={queue.isLoading}
          columns={columns}
          dataSource={queue.data?.list ?? []}
          locale={{ emptyText: <Empty description="没有需要处理的附件" /> }}
          pagination={{
            current: page,
            pageSize: 10,
            total: queue.data?.total ?? 0,
            onChange: setPage,
          }}
        />
      </Card>

      <Modal
        title="人工复核"
        open={Boolean(reviewTarget)}
        onCancel={() => setReviewTarget(undefined)}
        onOk={() => submitReview.mutate()}
        okText="保存结论"
        confirmLoading={submitReview.isPending}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Typography.Text type="secondary">
            {reviewTarget?.original_name} · {reviewTarget?.uploader} ·{' '}
            {reviewTarget?.tenant_name ?? `#${reviewTarget?.tenant_id}`}
          </Typography.Text>
          <Select
            style={{ width: '100%' }}
            value={reviewDecision}
            onChange={(value) => setReviewDecision(value)}
            options={[
              { value: 'approved', label: '通过' },
              { value: 'rejected', label: '驳回' },
            ]}
          />
          {reviewDecision === 'rejected' ? (
            <Select
              mode="multiple"
              style={{ width: '100%' }}
              placeholder="驳回原因（可多选）"
              value={rejectCategories}
              onChange={setRejectCategories}
              options={REJECT_CATEGORIES}
            />
          ) : null}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            结论变更会写入审核日志，可追溯；驳回后仅上传者与租户管理员可见。
          </Typography.Text>
        </Space>
      </Modal>

      <Modal
        title="审核日志"
        open={Boolean(logsTarget)}
        onCancel={() => setLogsTarget(undefined)}
        footer={null}
        width={640}
      >
        <Table<ModerationLogEntry>
          rowKey="id"
          size="small"
          loading={logs.isLoading}
          dataSource={logs.data ?? []}
          pagination={false}
          columns={[
            { title: '时间', dataIndex: 'created_at', render: (v: string) => new Date(v).toLocaleString('zh-CN') },
            { title: '结论', dataIndex: 'decision' },
            { title: 'provider', dataIndex: 'provider' },
            { title: '来源', dataIndex: 'source' },
            { title: '耗时(ms)', dataIndex: 'elapsed_ms' },
            {
              title: '分类',
              dataIndex: 'categories',
              render: (value: string[]) => (value ?? []).join(', ') || '-',
            },
          ]}
        />
      </Modal>
    </PageShell>
  );
}
