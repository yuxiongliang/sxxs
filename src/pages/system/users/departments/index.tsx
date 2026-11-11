import {
  ApartmentOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useState } from 'react';
import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  updateDepartment,
} from '@/services/system/api';
import type { DepartmentRecord } from '@/services/system/types';
import SettingPage from '../../components/SettingPage';

const DepartmentManagementPage: React.FC = () => {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<DepartmentRecord>();

  const { data, isLoading } = useQuery({
    queryKey: ['departments', 'page'],
    queryFn: () => listDepartments({ pageSize: 200 }),
  });

  const openCreate = () => {
    setEditing(undefined);
    form.resetFields();
    form.setFieldsValue({ status: 'active', sort: 0 });
    setEditOpen(true);
  };

  const openEdit = (record: DepartmentRecord) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue(record);
    setEditOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateDepartment(editing.id, values);
        message.success('部门已更新');
      } else {
        await createDepartment(values);
        message.success('部门已创建');
      }
      setEditOpen(false);
      await queryClient.invalidateQueries({ queryKey: ['departments'] });
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.message || '保存失败');
    }
  };

  const handleDelete = async (record: DepartmentRecord) => {
    try {
      await deleteDepartment(record.id);
      message.success('部门已删除');
      await queryClient.invalidateQueries({ queryKey: ['departments'] });
    } catch (error: any) {
      message.error(error?.message || '删除失败');
    }
  };

  const columns: ColumnsType<DepartmentRecord> = [
    {
      title: '部门名称',
      dataIndex: 'name',
      render: (_, record) => (
        <Space>
          <ApartmentOutlined style={{ color: '#1677ff' }} />
          <span style={{ fontWeight: 600 }}>{record.name}</span>
        </Space>
      ),
    },
    { title: '编码', dataIndex: 'code', render: (value) => value || '-' },
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
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该部门？"
            onConfirm={() => handleDelete(record)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <SettingPage
      title="部门管理"
      subTitle="维护组织部门字典，供用户管理选择"
      icon={<ApartmentOutlined />}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增部门
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
        title={editing ? '编辑部门' : '新增部门'}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleSave}
        destroyOnHidden
        forceRender
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="部门名称"
            name="name"
            rules={[{ required: true, message: '请输入部门名称' }]}
          >
            <Input placeholder="例如：平台运营部" />
          </Form.Item>
          <Form.Item label="编码" name="code">
            <Input
              placeholder="可选，例如：platform-ops"
              disabled={!!editing}
            />
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
    </SettingPage>
  );
};

export default DepartmentManagementPage;
