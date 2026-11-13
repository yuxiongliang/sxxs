import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Checkbox,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import {
  createRole,
  deleteRole,
  getRolePermissions,
  listRoles,
  updateRole,
  updateRolePermissions,
} from '@/services/system/api';
import type { RolePermissions, RoleRecord } from '@/services/system/types';
import SettingPage from '../../components/SettingPage';

const RoleManagementPage: React.FC = () => {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<RoleRecord>();
  const [permOpen, setPermOpen] = useState(false);
  const [permRole, setPermRole] = useState<RoleRecord>();
  const [permData, setPermData] = useState<RolePermissions>();
  const [permSelected, setPermSelected] = useState<string[]>([]);
  const [permSaving, setPermSaving] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['roles', 'page'],
    queryFn: () => listRoles({ pageSize: 200 }),
  });

  const openCreate = () => {
    setEditing(undefined);
    form.resetFields();
    form.setFieldsValue({ status: 'active', sort: 0 });
    setEditOpen(true);
  };

  const openEdit = (record: RoleRecord) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue(record);
    setEditOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateRole(editing.id, values);
        message.success('角色已更新');
      } else {
        await createRole(values);
        message.success('角色已创建');
      }
      setEditOpen(false);
      await queryClient.invalidateQueries({ queryKey: ['roles'] });
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.message || '保存失败');
    }
  };

  const openPermissions = async (record: RoleRecord) => {
    setPermRole(record);
    setPermOpen(true);
    const data = await getRolePermissions(record.id);
    setPermData(data);
    setPermSelected(data.selected);
  };

  const handleSavePermissions = async () => {
    if (!permRole) return;
    setPermSaving(true);
    try {
      await updateRolePermissions(permRole.id, permSelected);
      message.success('角色权限已更新');
      setPermOpen(false);
    } finally {
      setPermSaving(false);
    }
  };

  const handleDelete = async (record: RoleRecord) => {
    try {
      await deleteRole(record.id);
      message.success('角色已删除');
      await queryClient.invalidateQueries({ queryKey: ['roles'] });
    } catch (error: any) {
      message.error(error?.message || '删除失败');
    }
  };

  const columns: ColumnsType<RoleRecord> = [
    {
      title: '角色名称',
      dataIndex: 'name',
      render: (_, record) => (
        <Space>
          <SafetyCertificateOutlined style={{ color: '#1677ff' }} />
          <Space orientation="vertical" size={0}>
            <Space size={6}>
              <span style={{ fontWeight: 600 }}>{record.name}</span>
              {record.tenant_id == null ? (
                <Tag color="blue">系统内置</Tag>
              ) : (
                <Tag>本租户</Tag>
              )}
            </Space>
            <span style={{ color: '#8c8c8c', fontSize: 12 }}>
              {record.code}
            </span>
          </Space>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      render: (value) => value || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'success' : 'default'}>
          {value === 'active' ? '启用' : '停用'}
        </Tag>
      ),
    },
    { title: '排序', dataIndex: 'sort', width: 80 },
    {
      title: '操作',
      width: 150,
      render: (_, record) => {
        // 系统内置角色全租户共享、只读：后端会直接 403，按钮就不该可点
        const readonly = record.tenant_id == null;
        if (readonly) {
          return (
            <Tooltip title="系统内置角色为全租户共享、只读；如需调整请新增一个本租户角色">
              <Space>
                <Button type="link" size="small" disabled>
                  权限
                </Button>
                <Button type="link" size="small" disabled>
                  编辑
                </Button>
                <Button type="link" size="small" disabled>
                  删除
                </Button>
              </Space>
            </Tooltip>
          );
        }
        return (
          <Space>
            <Button
              type="link"
              size="small"
              onClick={() => openPermissions(record)}
            >
              权限
            </Button>
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            >
              编辑
            </Button>
            <Popconfirm
              title="确定删除该角色？"
              onConfirm={() => handleDelete(record)}
            >
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <SettingPage
      title="角色管理"
      subTitle="维护角色字典，供用户管理选择"
      icon={<SafetyCertificateOutlined />}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增角色
        </Button>
      }
    >
      <Card>
        <Table
          rowKey="id"
          loading={isLoading}
          columns={columns}
          dataSource={data?.list ?? []}
          pagination={{ pageSize: 20, showSizeChanger: true }}
        />
      </Card>

      <Modal
        title={editing ? '编辑角色' : '新增角色'}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleSave}
        destroyOnHidden
        forceRender
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="角色编码"
            name="code"
            rules={[{ required: true, message: '请输入角色编码' }]}
          >
            <Input placeholder="例如：editor" disabled={!!editing} />
          </Form.Item>
          <Form.Item
            label="角色名称"
            name="name"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="例如：内容编辑" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item label="状态" name="status" style={{ flex: 1 }}>
              <Select
                options={[
                  { label: '启用', value: 'active' },
                  { label: '停用', value: 'disabled' },
                ]}
              />
            </Form.Item>
            <Form.Item label="排序" name="sort" style={{ flex: 1 }}>
              <InputNumber min={0} max={9999} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal
        title={permRole ? `角色权限：${permRole.name}` : '角色权限'}
        open={permOpen}
        onCancel={() => setPermOpen(false)}
        onOk={handleSavePermissions}
        confirmLoading={permSaving}
        width={760}
        destroyOnHidden
      >
        {Object.entries(
          (permData?.all ?? []).reduce<
            Record<string, { code: string; name: string }[]>
          >((groups, item) => {
            groups[item.module] = groups[item.module] || [];
            groups[item.module].push({ code: item.code, name: item.name });
            return groups;
          }, {}),
        ).map(([module, items]) => (
          <div key={module}>
            <Divider titlePlacement="start">{module}</Divider>
            <Checkbox.Group
              value={permSelected}
              onChange={(values) => setPermSelected(values as string[])}
              options={items.map((item) => ({
                label: `${item.name}（${item.code}）`,
                value: item.code,
              }))}
            />
          </div>
        ))}
      </Modal>
    </SettingPage>
  );
};

export default RoleManagementPage;
