import { AuditOutlined, ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import type { AuditLogRecord } from '@/services/system/audit';
import { listAuditActions, listAuditLogs } from '@/services/system/audit';
import SettingPage from '../components/SettingPage';

const actionColor = (action: string) =>
  action.includes('created')
    ? 'blue'
    : action.includes('paid')
      ? 'green'
      : action.includes('cancel') ||
          action.includes('reject') ||
          action.includes('suspend')
        ? 'red'
        : action.includes('moderated')
          ? 'volcano'
          : 'default';

const AuditPage: React.FC = () => {
  const [action, setAction] = useState<string>();
  const [targetType, setTargetType] = useState<string>();
  const [targetId, setTargetId] = useState<string>();
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<AuditLogRecord>();

  const actions = useQuery({
    queryKey: ['audit-actions'],
    queryFn: listAuditActions,
  });
  const logs = useQuery({
    queryKey: ['audit-logs', action, targetType, targetId, page],
    queryFn: () =>
      listAuditLogs({
        current: page,
        pageSize: 20,
        action,
        target_type: targetType,
        target_id: targetId || undefined,
      }),
  });

  const columns: ColumnsType<AuditLogRecord> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 190,
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      title: '动作',
      dataIndex: 'action',
      width: 220,
      render: (value: string) => <Tag color={actionColor(value)}>{value}</Tag>,
    },
    {
      title: '对象',
      key: 'target',
      width: 200,
      render: (_, record) => (
        <Space size={4}>
          <Typography.Text>{record.target_type}</Typography.Text>
          <Typography.Text type="secondary">
            #{record.target_id}
          </Typography.Text>
        </Space>
      ),
    },
    { title: '操作人', dataIndex: 'actor_id', width: 100 },
    { title: '租户', dataIndex: 'tenant_id', width: 90 },
    {
      title: '来源 IP',
      dataIndex: 'ip',
      width: 140,
      render: (value: string) => value || '-',
    },
    {
      title: '操作',
      width: 90,
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => setDetail(record)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <SettingPage
      title="审计日志"
      subTitle="订单支付、退款、提现结算与权限变更的全链路留痕"
      icon={<AuditOutlined />}
      extra={
        <Button icon={<ReloadOutlined />} onClick={() => logs.refetch()}>
          刷新
        </Button>
      }
    >
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            allowClear
            showSearch
            placeholder="动作"
            style={{ width: 240 }}
            value={action}
            onChange={(value) => {
              setAction(value);
              setPage(1);
            }}
            options={(actions.data ?? []).map((item) => ({
              value: item,
              label: item,
            }))}
          />
          <Input
            allowClear
            placeholder="对象类型，如 order"
            style={{ width: 200 }}
            value={targetType}
            onChange={(event) => {
              setTargetType(event.target.value || undefined);
              setPage(1);
            }}
          />
          <Input
            allowClear
            placeholder="对象 ID"
            style={{ width: 160 }}
            value={targetId}
            onChange={(event) => {
              setTargetId(event.target.value || undefined);
              setPage(1);
            }}
          />
        </Space>
        <Table
          rowKey="id"
          loading={logs.isLoading}
          columns={columns}
          dataSource={logs.data?.list ?? []}
          pagination={{
            current: page,
            pageSize: 20,
            total: logs.data?.total ?? 0,
            onChange: setPage,
            showSizeChanger: false,
          }}
        />
      </Card>

      <Drawer
        title={`审计详情 #${detail?.id ?? ''}`}
        open={!!detail}
        width={640}
        onClose={() => setDetail(undefined)}
      >
        {detail ? (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="动作">
                {detail.action}
              </Descriptions.Item>
              <Descriptions.Item label="对象">
                {detail.target_type} / {detail.target_id}
              </Descriptions.Item>
              <Descriptions.Item label="操作人">
                {detail.actor_id ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="租户">
                {detail.tenant_id ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="IP">
                {detail.ip ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Trace">
                {detail.trace_id ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="时间">
                {new Date(detail.created_at).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>
            <Typography.Title level={5} style={{ marginTop: 16 }}>
              变更前
            </Typography.Title>
            <pre
              style={{ background: '#fafafa', padding: 12, borderRadius: 8 }}
            >
              {JSON.stringify(detail.before ?? null, null, 2)}
            </pre>
            <Typography.Title level={5}>变更后</Typography.Title>
            <pre
              style={{ background: '#fafafa', padding: 12, borderRadius: 8 }}
            >
              {JSON.stringify(detail.after ?? null, null, 2)}
            </pre>
          </>
        ) : null}
      </Drawer>
    </SettingPage>
  );
};

export default AuditPage;
