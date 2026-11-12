import { ReloadOutlined, TeamOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Input,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { PlatformUserRecord } from '@/services/api';
import { listPlatformUsers } from '@/services/api';

export default function PlatformUsersPage() {
  const [keyword, setKeyword] = useState('');
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
    { title: '昵称', dataIndex: 'nickname', width: 160 },
    { title: '账号', dataIndex: 'username', width: 220, ellipsis: true },
    { title: '邮箱', dataIndex: 'email', width: 240, ellipsis: true },
    {
      title: '角色',
      dataIndex: 'role',
      width: 140,
      render: (value: string) => (
        <Space size={4}>
          <Tag>{value}</Tag>
          {value === 'platform_admin' ? <Tag color="gold">平台</Tag> : null}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'green' : 'default'}>{value}</Tag>
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
