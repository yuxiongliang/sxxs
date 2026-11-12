import {
  BellOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  MailOutlined,
  MessageOutlined,
  NotificationOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Col,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
} from 'antd';
import { Alert } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import {
  getNotificationStats,
  listNotifications,
  retryNotification,
} from '@/services/system/api';
import type { NotificationRecord } from '@/services/system/types';
import SettingPage from '../components/SettingPage';
import {
  CHANNEL_OPTIONS,
  NOTIFICATION_STATUS_OPTIONS,
  formatDateTime,
  optionColor,
  optionLabel,
} from '../utils';

const AUDIENCE_OPTIONS = [
  { label: '全部用户', value: 'all' },
  { label: '管理员', value: 'role:admin' },
  { label: '运营人员', value: 'role:operator' },
  { label: '只读用户', value: 'role:viewer' },
  { label: '自定义人群', value: 'custom' },
];

const channelIcon = (channel: string) => {
  if (channel === 'sms') return <MessageOutlined />;
  if (channel === 'email') return <MailOutlined />;
  return <BellOutlined />;
};

const NotificationsPage: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('records');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [channel, setChannel] = useState<string>('all');
  const [status, setStatus] = useState<string>('all');

  const { data: stats } = useQuery({
    queryKey: ['notification-stats'],
    queryFn: getNotificationStats,
  });
  const { data, isLoading } = useQuery({
    queryKey: ['notifications', page, pageSize, channel, status],
    queryFn: () =>
      listNotifications({ current: page, pageSize, channel, status }),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
    queryClient.invalidateQueries({ queryKey: ['notification-stats'] });
  };

const handleRetry = async (record: NotificationRecord) => {
    try {
      await retryNotification(record.id);
      message.success('已重新发送');
      refresh();
    } catch (error: any) {
      message.error(error?.message || '重试失败');
    }
  };

  const columns: ColumnsType<NotificationRecord> = [
    {
      title: '通知标题',
      dataIndex: 'title',
      render: (_, record) => (
        <Space>
          <span style={{ fontSize: 18, color: '#1677ff' }}>
            {channelIcon(record.channel)}
          </span>
          <div>
            <div style={{ fontWeight: 600 }}>{record.title}</div>
            <div style={{ color: '#8c8c8c', fontSize: 12 }}>
              {record.template || '自定义模板'}
            </div>
          </div>
        </Space>
      ),
    },
    {
      title: '渠道',
      dataIndex: 'channel',
      width: 100,
      render: (value: string) => (
        <Tag color={optionColor(CHANNEL_OPTIONS, value)}>
          {optionLabel(CHANNEL_OPTIONS, value)}
        </Tag>
      ),
    },
    {
      title: '受众',
      dataIndex: 'audience',
      width: 140,
      render: (value: string) =>
        AUDIENCE_OPTIONS.find((item) => item.value === value)?.label ?? value,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: string) => (
        <Tag color={optionColor(NOTIFICATION_STATUS_OPTIONS, value)}>
          {optionLabel(NOTIFICATION_STATUS_OPTIONS, value)}
        </Tag>
      ),
    },
    {
      title: '成功 / 总数',
      dataIndex: 'success_count',
      width: 120,
      render: (_, record) => `${record.success_count} / ${record.total}`,
    },
    {
      title: '发送时间',
      dataIndex: 'sent_at',
      width: 170,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) =>
        record.status === 'failed' ? (
          <Button type="link" onClick={() => handleRetry(record)}>
            重试
          </Button>
        ) : null,
    },
  ];

  return (
    <SettingPage
      title="触达通知"
      subTitle="通知模板由平台统一管理 · 这里查看发送记录与渠道开关"
      icon={<NotificationOutlined />}
      extra={
        <Button icon={<ReloadOutlined />} onClick={refresh}>
          刷新
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="通知模板由平台统一管理"
        description="平台负责模板与渠道策略；租户侧只保留发送记录、可用模板说明与渠道开关。站内信为强制渠道（欠费/安全类通知），不可关闭。"
      />
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="通知总数"
              value={stats?.total ?? 0}
              prefix={<NotificationOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="发送成功"
              value={stats?.success ?? 0}
              prefix={<CheckCircleOutlined />}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="发送失败"
              value={stats?.failed ?? 0}
              prefix={<CloseCircleOutlined />}
              styles={{ content: { color: '#ff4d4f' } }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="待发送"
              value={stats?.pending ?? 0}
              prefix={<ClockCircleOutlined />}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
{
              key: 'records',
              label: '发送记录',
              children: (
                <>
                  <Space wrap style={{ marginBottom: 16 }}>
                    <Select
                      value={channel}
                      style={{ width: 140 }}
                      onChange={(value) => {
                        setChannel(value);
                        setPage(1);
                      }}
                      options={[
                        { label: '全部渠道', value: 'all' },
                        ...CHANNEL_OPTIONS.map(({ label, value }) => ({
                          label,
                          value,
                        })),
                      ]}
                    />
                    <Select
                      value={status}
                      style={{ width: 140 }}
                      onChange={(value) => {
                        setStatus(value);
                        setPage(1);
                      }}
                      options={[
                        { label: '全部状态', value: 'all' },
                        ...NOTIFICATION_STATUS_OPTIONS.map(
                          ({ label, value }) => ({ label, value }),
                        ),
                      ]}
                    />
                    <Button icon={<ReloadOutlined />} onClick={refresh}>
                      刷新
                    </Button>
                  </Space>
                  <Table
                    rowKey="id"
                    loading={isLoading}
                    columns={columns}
                    dataSource={data?.list ?? []}
                    pagination={{
                      current: page,
                      pageSize,
                      total: data?.total ?? 0,
                      showSizeChanger: true,
                      onChange: (nextPage, nextPageSize) => {
                        setPage(nextPage);
                        setPageSize(nextPageSize);
                      },
                    }}
                  />
                </>
              ),
            },
          ]}
        />
      </Card>
    </SettingPage>
  );
};

export default NotificationsPage;
