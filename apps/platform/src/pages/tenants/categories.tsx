import {
  AppstoreOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { ServiceCategoryRecord } from '@/services/api';
import {
  createServiceCategory,
  listServiceCategories,
  updateServiceCategory,
} from '@/services/api';

/** bps（万分比）→ 百分比展示：500 → 5% */
const bpsToPercent = (bps: number) =>
  `${(bps / 100).toFixed(bps % 100 === 0 ? 0 : 2)}%`;
/** 百分比 → bps：5.25% → 525 */
const percentToBps = (value: number | null | undefined) =>
  Math.round((value ?? 0) * 100);

interface CategoryFormValues {
  code: string;
  name: string;
  description?: string;
  commission_percent: number;
  sort?: number;
}

export default function ServiceCategoriesPage() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<CategoryFormValues>();
  const [editing, setEditing] = useState<ServiceCategoryRecord | null>(null);
  const [open, setOpen] = useState(false);

  const categories = useQuery({
    queryKey: ['service-categories', 'all'],
    queryFn: () => listServiceCategories(true),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['service-categories'] });
    // 租户列表上的类目列也要跟着变
    queryClient.invalidateQueries({ queryKey: ['platform-tenants-plan'] });
  };

  const save = useMutation({
    mutationFn: async (values: CategoryFormValues) => {
      const payload = {
        name: values.name,
        description: values.description ?? '',
        commission_bps: percentToBps(values.commission_percent),
        sort: values.sort ?? 0,
      };
      if (editing) return updateServiceCategory(editing.id, payload);
      return createServiceCategory({ ...payload, code: values.code });
    },
    onSuccess: () => {
      message.success(editing ? '类目已更新' : '类目已创建');
      setOpen(false);
      setEditing(null);
      form.resetFields();
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const archive = useMutation({
    mutationFn: (record: ServiceCategoryRecord) =>
      updateServiceCategory(record.id, {
        status: record.status === 'active' ? 'archived' : 'active',
      }),
    onSuccess: (record) => {
      message.success(record.status === 'active' ? '类目已启用' : '类目已归档');
      refresh();
    },
    onError: (error: Error) => message.error(error.message),
  });

  const columns: ColumnsType<ServiceCategoryRecord> = [
    { title: '类目名称', dataIndex: 'name', width: 200 },
    {
      title: '编码',
      dataIndex: 'code',
      width: 160,
      render: (value: string) => (
        <Typography.Text code>{value}</Typography.Text>
      ),
    },
    {
      title: '抽佣比例',
      dataIndex: 'commission_bps',
      width: 120,
      render: (value: number) =>
        value > 0 ? (
          <Tag color="gold">{bpsToPercent(value)}</Tag>
        ) : (
          <Tag>不抽佣</Tag>
        ),
    },
    {
      title: '租户数',
      dataIndex: 'tenant_count',
      width: 100,
      render: (value?: number) => value ?? 0,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'active' ? 'green' : 'default'}>
          {value === 'active' ? '启用' : '已归档'}
        </Tag>
      ),
    },
    { title: '排序', dataIndex: 'sort', width: 80 },
    {
      title: '备注',
      dataIndex: 'description',
      render: (value: string) => (
        <Typography.Text type="secondary">{value || '—'}</Typography.Text>
      ),
    },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size={2}>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setEditing(record);
              form.setFieldsValue({
                code: record.code,
                name: record.name,
                description: record.description,
                commission_percent: record.commission_bps / 100,
                sort: record.sort,
              });
              setOpen(true);
            }}
          >
            编辑
          </Button>
          <Popconfirm
            title={
              record.status === 'active'
                ? '归档后不能再分配给新租户（已归属的租户不受影响），确认？'
                : '重新启用该类目？'
            }
            onConfirm={() => archive.mutate(record)}
          >
            <Button
              type="link"
              size="small"
              danger={record.status === 'active'}
            >
              {record.status === 'active' ? '归档' : '启用'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="服务类目"
      subTitle="平台级业务类目：决定租户归属，以及平台按多少比例向该租户抽佣"
      icon={<AppstoreOutlined />}
      extra={
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => categories.refetch()}
          >
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null);
              form.resetFields();
              form.setFieldsValue({ commission_percent: 0, sort: 0 });
              setOpen(true);
            }}
          >
            新建类目
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="类目决定抽佣比例，改比例只影响后续计算"
        description="开通租户时把租户归到某个类目；买断套餐的租户不抽佣（那是套餐侧的性质，不写回类目）。归档类目不会影响已经归属的租户，只是不能再分配给新租户。"
      />

      <Card>
        <Table<ServiceCategoryRecord>
          rowKey="id"
          size="small"
          loading={categories.isLoading}
          columns={columns}
          dataSource={categories.data ?? []}
          pagination={false}
        />
      </Card>

      <Modal
        title={editing ? `编辑类目 ${editing.code}` : '新建类目'}
        open={open}
        onCancel={() => {
          setOpen(false);
          setEditing(null);
        }}
        onOk={() => form.submit()}
        confirmLoading={save.isPending}
        okText="保存"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => save.mutate(values)}
        >
          <Form.Item
            name="code"
            label="编码"
            rules={[
              {
                required: true,
                pattern: /^[a-z0-9-]+$/,
                message: '仅小写字母/数字/中划线',
              },
            ]}
          >
            <Input disabled={Boolean(editing)} placeholder="second-hand" />
          </Form.Item>
          <Form.Item name="name" label="类目名称" rules={[{ required: true }]}>
            <Input placeholder="二手交易" />
          </Form.Item>
          <Form.Item
            name="commission_percent"
            label="抽佣比例（%）"
            extra="0 表示不抽佣；买断套餐的租户无论类目如何都是 0。"
          >
            <InputNumber
              min={0}
              max={100}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item name="sort" label="排序（小的在前）">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="description" label="备注">
            <Input placeholder="这个类目怎么界定，方便运营判断归属" />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}
