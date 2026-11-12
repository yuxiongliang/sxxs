import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type { NotificationTemplateRecord } from '@/services/api';
import {
  listNotificationTemplates,
  saveNotificationTemplate,
} from '@/services/api';

const VARIABLE_SAMPLES: Record<string, string> = {
  tenant_name: '示例站点',
  tenant_short_name: '示例',
  tenant_domain: 'shop.example.com',
  buyer_name: '张三',
  order_no: 'SO-20260101-001',
  amount: '¥199.00',
  site_url: 'https://shop.example.com',
  support_email: 'support@example.com',
};

function preview(text: string): string {
  return (text || '').replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, name) =>
    VARIABLE_SAMPLES[name] ?? `{{${name}}}`,
  );
}

interface FormValues {
  code: string;
  name: string;
  channel: string;
  subject: string;
  body: string;
  enabled: boolean;
  mandatory: boolean;
}

function TemplatePanel({ scope }: { scope: 'platform' | 'tenant' }) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [editing, setEditing] = useState<NotificationTemplateRecord | null>(null);
  const [open, setOpen] = useState(false);

  const templates = useQuery({
    queryKey: ['notification-templates', scope],
    queryFn: () => listNotificationTemplates(scope),
  });

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      saveNotificationTemplate(scope, values.code, {
        name: values.name,
        channel: values.channel,
        subject: values.subject ?? '',
        body: values.body ?? '',
        enabled: values.enabled,
        mandatory: values.mandatory,
      }),
    onSuccess: () => {
      message.success('模板已保存');
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ['notification-templates', scope] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const columns: ColumnsType<NotificationTemplateRecord> = [
    { title: '编码', dataIndex: 'code', width: 180 },
    { title: '名称', dataIndex: 'name', width: 180 },
    {
      title: '渠道',
      dataIndex: 'channel',
      width: 100,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: '变量',
      dataIndex: 'variables',
      render: (value: string[]) => (value ?? []).map((name) => <Tag key={name}>{name}</Tag>),
    },
    {
      title: '状态',
      width: 150,
      render: (_, record) => (
        <Space>
          <Tag color={record.enabled ? 'green' : 'default'}>
            {record.enabled ? '启用' : '停用'}
          </Tag>
          {record.mandatory ? <Tag color="red">强制</Tag> : null}
        </Space>
      ),
    },
    {
      title: '操作',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => {
            setEditing(record);
            form.setFieldsValue(record);
            setOpen(true);
          }}
        >
          编辑
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        title={
          scope === 'platform'
            ? '平台 → 租户管理员：模板里的 {{tenant_name}} 渲染成平台名称'
            : '租户 → 买家/卖家：模板里的 {{tenant_name}} 渲染成租户自己的站点名'
        }
        description="变量只能使用白名单内的名称；发送前会校验，变量缺失会拦下而不是原样发出。"
      />
      <Space>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditing(null);
            form.resetFields();
            form.setFieldsValue({ enabled: true, mandatory: false, channel: 'inbox' });
            setOpen(true);
          }}
        >
          新建模板
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => templates.refetch()}
        >
          刷新
        </Button>
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={templates.isLoading}
        columns={columns}
        dataSource={templates.data ?? []}
        pagination={false}
      />

      <Modal
        title={editing ? `编辑模板 ${editing.code}` : '新建模板'}
        open={open}
        width={720}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={save.isPending}
        okText="保存"
      >
        <Form form={form} layout="vertical" onFinish={(values) => save.mutate(values)}>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input disabled={Boolean(editing)} placeholder="order_paid" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="订单支付成功" />
          </Form.Item>
          <Form.Item name="channel" label="渠道">
            <Select
              options={[
                { value: 'inbox', label: '站内信' },
                { value: 'sms', label: '短信' },
                { value: 'email', label: '邮件' },
              ]}
            />
          </Form.Item>
          <Form.Item name="subject" label="标题/主题">
            <Input placeholder="{{tenant_name}} 订单支付成功" />
          </Form.Item>
          <Form.Item
            name="body"
            label="正文"
            extra="可用变量：tenant_name / tenant_short_name / tenant_domain / buyer_name / order_no / amount / site_url / support_email"
          >
            <Input.TextArea rows={5} placeholder="你好 {{buyer_name}}，订单 {{order_no}} 已支付" />
          </Form.Item>
          <Space size={24}>
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="mandatory"
              label="强制送达（租户不可关闭）"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item label="预览" shouldUpdate>
            {() => (
              <Card size="small">
                <Typography.Text strong>
                  {preview(form.getFieldValue('subject') ?? '')}
                </Typography.Text>
                <div style={{ marginTop: 8 }}>
                  <Typography.Text>
                    {preview(form.getFieldValue('body') ?? '')}
                  </Typography.Text>
                </div>
              </Card>
            )}
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

export default function NotificationTemplatesPage() {
  return (
    <PageShell
      title="通知中心"
      subTitle="平台统一管理通知渠道与模板；租户只读自己的发送记录"
    >
      <Card>
        <Tabs
          items={[
            {
              key: 'tenant',
              label: '租户 → 买家/卖家',
              children: <TemplatePanel scope="tenant" />,
            },
            {
              key: 'platform',
              label: '平台 → 租户',
              children: <TemplatePanel scope="platform" />,
            },
          ]}
        />
      </Card>
    </PageShell>
  );
}
