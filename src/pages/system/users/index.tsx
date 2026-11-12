import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Avatar,
  Button,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
} from 'antd';
import dayjs from 'dayjs';
import React, { useMemo, useRef, useState } from 'react';
import {
  createUser,
  deleteUser,
  listDepartments,
  listRoles,
  listUsers,
  resetUserPassword,
  updateUser,
} from '@/services/system/api';
import type {
  DepartmentRecord,
  RoleRecord,
  UserRecord,
} from '@/services/system/types';
import SettingPage from '../components/SettingPage';
import {
  formatDate,
  formatDateTime,
  GENDER_OPTIONS,
  optionLabel,
  USER_STATUS_OPTIONS,
} from '../utils';

const roleColor = (role: string) => {
  if (role === 'admin') return 'red';
  if (role === 'operator') return 'blue';
  return 'default';
};

const UserManagement: React.FC = () => {
  const actionRef = useRef<ActionType | null>(null);
  const [form] = Form.useForm();
  const { message, modal } = App.useApp();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<UserRecord>();

  const { data: departments } = useQuery({
    queryKey: ['departments', 'active'],
    queryFn: () => listDepartments({ pageSize: 200, status: 'active' }),
  });
  const { data: roles } = useQuery({
    queryKey: ['roles', 'active'],
    queryFn: () => listRoles({ pageSize: 200, status: 'active' }),
  });

  const departmentMap = useMemo(
    () =>
      new Map<number, DepartmentRecord>(
        (departments?.list ?? []).map((item) => [item.id, item]),
      ),
    [departments],
  );
  const roleMap = useMemo(
    () =>
      new Map<string, RoleRecord>(
        (roles?.list ?? []).map((item) => [item.code, item]),
      ),
    [roles],
  );

  const openCreate = () => {
    setEditing(undefined);
    form.resetFields();
    form.setFieldsValue({ role: 'viewer', status: 'active' });
    setOpen(true);
  };

  const openEdit = (record: UserRecord) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue({
      ...record,
      birthday: record.birthday ? dayjs(record.birthday) : undefined,
      password: undefined,
    });
    setOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const payload = {
      ...values,
      birthday: values.birthday
        ? values.birthday.format('YYYY-MM-DD')
        : undefined,
    };
    if (editing && !payload.password) delete payload.password;
    setSaving(true);
    try {
      if (editing) {
        await updateUser(editing.id, payload);
        message.success('用户信息已更新');
      } else {
        await createUser(payload);
        message.success('用户创建成功');
      }
      setOpen(false);
      actionRef.current?.reload();
    } catch (error: any) {
      message.error(error?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleResetPassword = (record: UserRecord) => {
    modal.confirm({
      title: '重置密码',
      content: `确定将 ${record.nickname} 的密码重置为随机临时密码吗？`,
      onOk: async () => {
        const result = await resetUserPassword(record.id);
        modal.success({
          title: '密码已重置',
          content: `临时密码：${result.password}（请让用户首次登录后立即修改）`,
        });
      },
    });
  };

  const handleToggleStatus = async (record: UserRecord) => {
    try {
      await updateUser(record.id, {
        status: record.status === 'active' ? 'disabled' : 'active',
      });
      message.success(record.status === 'active' ? '用户已停用' : '用户已启用');
      actionRef.current?.reload();
    } catch (error: any) {
      message.error(error?.message || '操作失败');
    }
  };

  const handleDelete = async (record: UserRecord) => {
    try {
      await deleteUser(record.id);
      message.success('用户已删除');
      actionRef.current?.reload();
    } catch (error: any) {
      message.error(error?.message || '删除失败');
    }
  };

  const columns: ProColumns<UserRecord>[] = [
    {
      title: '用户ID',
      dataIndex: 'public_id',
      search: false,
      fixed: 'left',
      width: 260,
      copyable: true,
      ellipsis: true,
      tooltip: '全站唯一的用户编号（随机 20 位），可直接粘到关键词框里搜索',
    },
    {
      // 展示登录账号（唯一、可直接对账），不再显示昵称
      title: '用户名',
      dataIndex: 'username',
      search: false,
      fixed: 'left',
      width: 280,
      copyable: true,
      ellipsis: true,
      render: (_, record) => (
        <Space>
          <Avatar style={{ background: '#1677ff' }}>
            {record.username?.slice(0, 1).toUpperCase()}
          </Avatar>
          <div style={{ fontWeight: 600 }}>{record.username}</div>
        </Space>
      ),
    },
    {
      title: '关键词',
      dataIndex: 'keyword',
      hideInTable: true,
      fieldProps: { placeholder: '用户名 / 昵称 / 邮箱 / 手机号 / 用户ID' },
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      search: false,
      copyable: true,
      width: 200,
    },
    { title: '手机号', dataIndex: 'phone', search: false, width: 130 },
    {
      title: '部门',
      dataIndex: 'department_id',
      valueType: 'select',
      width: 140,
      valueEnum: Object.fromEntries(
        (departments?.list ?? []).map((item) => [item.id, { text: item.name }]),
      ),
      render: (_, record) =>
        record.department_id
          ? (departmentMap.get(record.department_id)?.name ??
            record.department ??
            '-')
          : (record.department ?? '-'),
    },
    {
      title: '角色',
      dataIndex: 'role',
      valueType: 'select',
      width: 130,
      valueEnum: Object.fromEntries(
        (roles?.list ?? []).map((item) => [item.code, { text: item.name }]),
      ),
      render: (_, record) => (
        <Tag color={roleColor(record.role)}>
          {roleMap.get(record.role)?.name ?? record.role}
        </Tag>
      ),
    },
    {
      title: '性别',
      dataIndex: 'gender',
      search: false,
      width: 90,
      render: (_, record) => optionLabel(GENDER_OPTIONS, record.gender),
    },
    {
      title: '生日',
      dataIndex: 'birthday',
      search: false,
      width: 120,
      render: (_, record) => formatDate(record.birthday),
    },
    {
      title: '状态',
      dataIndex: 'status',
      valueType: 'select',
      width: 100,
      valueEnum: Object.fromEntries(
        USER_STATUS_OPTIONS.map((item) => [item.value, { text: item.label }]),
      ),
      render: (_, record) => (
        <Tag color={record.status === 'active' ? 'success' : 'default'}>
          {optionLabel(USER_STATUS_OPTIONS, record.status)}
        </Tag>
      ),
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      search: false,
      width: 160,
      render: (_, record) => formatDateTime(record.last_login_at),
    },
    {
      title: '操作',
      valueType: 'option',
      fixed: 'right',
      width: 260,
      render: (_, record) => [
        <Button
          key="edit"
          type="link"
          size="small"
          icon={<EditOutlined />}
          onClick={() => openEdit(record)}
        >
          编辑
        </Button>,
        <Button
          key="reset"
          type="link"
          size="small"
          onClick={() => handleResetPassword(record)}
        >
          重置密码
        </Button>,
        <Button
          key="toggle"
          type="link"
          size="small"
          onClick={() => handleToggleStatus(record)}
        >
          {record.status === 'active' ? '停用' : '启用'}
        </Button>,
        <Popconfirm
          key="delete"
          title="确定删除该用户？"
          description="删除后不可恢复"
          onConfirm={() => handleDelete(record)}
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>,
      ],
    },
  ];

  return (
    <SettingPage
      title="用户列表"
      subTitle="管理平台账号、部门、角色与访问状态"
      icon={<TeamOutlined />}
      extra={
        <Space wrap>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => actionRef.current?.reload()}
          >
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建用户
          </Button>
        </Space>
      }
    >
      <ProTable<UserRecord>
        rowKey="id"
        actionRef={actionRef}
        columns={columns}
        headerTitle="用户列表"
        search={{ labelWidth: 80 }}
        scroll={{ x: 1500 }}
        pagination={{ defaultPageSize: 10, showSizeChanger: true }}
        request={async (params) => {
          const result = await listUsers({
            current: params.current,
            pageSize: params.pageSize,
            keyword: params.keyword,
            role: params.role,
            status: params.status,
            department_id: params.department_id,
          });
          return { data: result.list, total: result.total, success: true };
        }}
      />

      <Modal
        title={editing ? '编辑用户' : '新建用户'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saving}
        destroyOnHidden
        forceRender
        width={640}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="登录用户名" disabled={!!editing} />
          </Form.Item>
          <Form.Item
            label="昵称"
            name="nickname"
            rules={[{ required: true, message: '请输入昵称' }]}
          >
            <Input placeholder="显示名称" />
          </Form.Item>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, type: 'email', message: '请输入合法邮箱' },
            ]}
          >
            <Input placeholder="name@example.com" />
          </Form.Item>
          <Form.Item label="手机号" name="phone">
            <Input placeholder="13800000000" />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item label="部门" name="department_id" style={{ flex: 1 }}>
              <Select
                allowClear
                placeholder="请选择部门"
                options={(departments?.list ?? []).map((item) => ({
                  label: item.name,
                  value: item.id,
                }))}
              />
            </Form.Item>
            <Form.Item
              label="角色"
              name="role"
              style={{ flex: 1 }}
              rules={[{ required: true, message: '请选择角色' }]}
            >
              <Select
                placeholder="请选择角色"
                options={(roles?.list ?? []).map((item) => ({
                  label: item.name,
                  value: item.code,
                }))}
              />
            </Form.Item>
          </Space>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item label="生日" name="birthday" style={{ flex: 1 }}>
              <DatePicker
                style={{ width: '100%' }}
                format="YYYY-MM-DD"
                disabledDate={(current) =>
                  current && current > dayjs().endOf('day')
                }
              />
            </Form.Item>
            <Form.Item label="性别" name="gender" style={{ flex: 1 }}>
              <Select allowClear options={GENDER_OPTIONS} />
            </Form.Item>
          </Space>
          <Form.Item
            label="登录密码"
            name="password"
            rules={[
              { required: !editing, message: '新建用户必须设置初始密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
            extra={
              editing
                ? '留空表示不修改密码'
                : '密码仅保存 argon2 哈希，不会明文返回'
            }
          >
            <Input.Password
              placeholder={editing ? '留空表示不修改' : '请输入初始密码'}
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select
              options={USER_STATUS_OPTIONS.map(({ label, value }) => ({
                label,
                value,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </SettingPage>
  );
};

export default UserManagement;
