import { ReloadOutlined, TeamOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { PlatformUserRecord } from '@/services/api';
import { listPlatformUsers, setPlatformUserStatus } from '@/services/api';
import { labelOf, USER_ROLE, USER_STATUS } from '@/utils/labels';

export default function PlatformUsersPage() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState('');

  const toggle = useMutation({
    mutationFn: (record: PlatformUserRecord) =>
      setPlatformUserStatus(
        record.id,
        record.status === 'active' ? 'disabled' : 'active',
      ),
    onSuccess: (result) => {
      message.success(result.status === 'active' ? '用户已启用' : '用户已停用');
      queryClient.invalidateQueries({ queryKey: ['platform-users'] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const users = useQuery({
    queryKey: ['platform-users', keyword],
    queryFn: () =>
      listPlatformUsers({ pageSize: 100, keyword: keyword || undefined }),
  });

  const columns: ColumnsType<PlatformUserRecord> = [
    {
      title: '用户ID',
      dataIndex: 'public_id',
      width: 250,
      render: (value: string) => (
        <Typography.Text copyable>{value}</Typography.Text>
      ),
    },
    {
      title: '用户名',
      dataIndex: 'username',
      width: 260,
      ellipsis: true,
      render: (value: string) => (
        <Typography.Text copyable>{value}</Typography.Text>
      ),
    },
    {
      title: '手机号',
      dataIndex: 'phone',
      width: 150,
      render: (value?: string | null) => value || '—',
    },
    { title: '邮箱', dataIndex: 'email', width: 240, ellipsis: true },
    {
      title: '角色',
      dataIndex: 'role',
      width: 140,
      render: (value: string) => (
        <Space size={4}>
          <Tag>{labelOf(USER_ROLE, value)}</Tag>
          {value === 'platform_admin' ? <Tag color="gold">平台</Tag> : null}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'green' : 'default'}>
          {labelOf(USER_STATUS, value)}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 110,
      render: (_, record) =>
        record.is_platform_admin ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            平台账号
          </Typography.Text>
        ) : (
          <Popconfirm
            title={
              record.status === 'active'
                ? '停用后该用户无法登录，确认？'
                : '重新启用该用户？'
            }
            onConfirm={() => toggle.mutate(record)}
          >
            <Button
              type="link"
              size="small"
              danger={record.status === 'active'}
              loading={toggle.isPending}
            >
              {record.status === 'active' ? '停用' : '启用'}
            </Button>
          </Popconfirm>
        ),
    },
  ];

  return (
    <PageShell
      title="用户"
      subTitle="全站用户（跨租户，只读）：租户控制台只能看到自己租户的成员"
      icon={<TeamOutlined />}
      extra={
        <Space>
          <Input.Search
            allowClear
            placeholder="用户名 / 昵称 / 邮箱 / 用户ID"
            style={{ width: 300 }}
            onSearch={(value) => setKeyword(value.trim())}
          />
          <Button icon={<ReloadOutlined />} onClick={() => users.refetch()}>
            刷新
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="这是平台级视图"
        description="只有 aud=platform 的 token 能访问；租户控制台的用户列表按 TenantMember 过滤，看不到别家租户的用户。"
      />
      <Card>
        <Table<PlatformUserRecord>
          rowKey="id"
          size="small"
          loading={users.isLoading}
          columns={columns}
          dataSource={users.data?.list ?? []}
          pagination={{
            pageSize: 20,
            total: users.data?.total,
            hideOnSinglePage: true,
          }}
        />
      </Card>
    </PageShell>
  );
}
