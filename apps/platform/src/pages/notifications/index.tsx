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
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import PageShell from '@/components/PageShell';
import type {
  NotificationTemplateRecord,
  NotificationTemplateScope,
  NotificationVariable,
} from '@/services/api';
import {
  listNotificationTemplates,
  listNotificationVariables,
  saveNotificationTemplate,
} from '@/services/api';

const SCOPE_META: Record<
  NotificationTemplateScope,
  { label: string; hint: string }
> = {
  tenant_buyer: {
    label: '租户 → 买家',
    hint: '收件人是买家：订单支付成功、发货提醒、退款结果。品牌用租户自己的站点名。',
  },
  tenant_seller: {
    label: '租户 → 卖家',
    hint: '收件人是店主/店员：新订单待处理、结算到账、审核结果。品牌同为租户站点名。',
  },
  platform: {
    label: '平台 → 租户',
    hint: '收件人是租户管理员：订阅到期、欠费、平台公告。品牌是平台本身。',
  },
};

interface FormValues {
  code: string;
  name: string;
  channel: string;
  subject: string;
  body: string;
  enabled: boolean;
  mandatory: boolean;
}

interface TemplatePanelProps {
  scope: NotificationTemplateScope;
  variables: NotificationVariable[];
}

function TemplatePanel({ scope, variables }: TemplatePanelProps) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [editing, setEditing] = useState<NotificationTemplateRecord | null>(
    null,
  );
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
      queryClient.invalidateQueries({
        queryKey: ['notification-templates', scope],
      });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const columns: ColumnsType<NotificationTemplateRecord> = [
    { title: '编码', dataIndex: 'code', width: 170 },
    { title: '名称', dataIndex: 'name', width: 170 },
    {
      title: '渠道',
      dataIndex: 'channel',
      width: 90,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: '变量（悬停看含义）',
      dataIndex: 'variables',
      render: (value: string[]) =>
        (value ?? []).map((name) => {
          const meta = variables.find((item) => item.name === name);
          return (
            <Tooltip
              key={name}
              title={
                meta ? `${meta.label}：${meta.description}` : '未登记的变量'
              }
            >
              <Tag color={meta ? undefined : 'red'}>{name}</Tag>
            </Tooltip>
          );
        }),
    },
    {
      title: '状态',
      width: 140,
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
      width: 90,
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
    <Space orientation="vertical" size={12} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        title={SCOPE_META[scope].label}
        description={SCOPE_META[scope].hint}
      />
      <Space>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditing(null);
            form.resetFields();
            form.setFieldsValue({
              enabled: true,
              mandatory: false,
              channel: 'inbox',
            });
            setOpen(true);
          }}
        >
          新建模板
        </Button>
        <Button icon={<ReloadOutlined />} onClick={() => templates.refetch()}>
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
        width={760}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={save.isPending}
        okText="保存"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => save.mutate(values)}
        >
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
          <Form.Item name="body" label="正文">
            <Input.TextArea
              rows={5}
              placeholder="你好 {{buyer_name}}，订单 {{order_no}} 已支付"
            />
          </Form.Item>
          <Space size={24}>
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="mandatory"
              label="强制送达"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </Space>
        </Form>

        <Card
          size="small"
          title="可用变量（中文释义）"
          style={{ marginTop: 8 }}
        >
          <Space orientation="vertical" size={2}>
            {variables.map((item) => (
              <Typography.Text key={item.name} style={{ fontSize: 12 }}>
                <Typography.Text code>{`{{${item.name}}}`}</Typography.Text>
                {` ${item.label} —— ${item.description}`}
              </Typography.Text>
            ))}
          </Space>
        </Card>
      </Modal>
    </Space>
  );
}

export default function NotificationTemplatesPage() {
  const variables = useQuery({
    queryKey: ['notification-variables'],
    queryFn: listNotificationVariables,
  });
  const catalog = variables.data ?? [];

  return (
    <PageShell
      title="通知中心"
      subTitle="模板按「谁发给谁」分三档，各自独立可见；变量只用白名单内的名称"
    >
      <Card title="可用变量" style={{ marginBottom: 16 }} size="small">
        <Table<NotificationVariable>
          rowKey="name"
          size="small"
          loading={variables.isLoading}
          pagination={false}
          dataSource={catalog}
          columns={[
            {
              title: '变量',
              dataIndex: 'name',
              width: 220,
              render: (value: string) => (
                <Typography.Text code>{`{{${value}}}`}</Typography.Text>
              ),
            },
            { title: '含义', dataIndex: 'label', width: 110 },
            { title: '说明', dataIndex: 'description' },
            {
              title: '示例值',
              dataIndex: 'example',
              width: 200,
              render: (value: string) => (
                <Typography.Text type="secondary">{value}</Typography.Text>
              ),
            },
          ]}
        />
      </Card>

      <Card>
        <Tabs
          items={(
            [
              'tenant_buyer',
              'tenant_seller',
              'platform',
            ] as NotificationTemplateScope[]
          ).map((scope) => ({
            key: scope,
            label: SCOPE_META[scope].label,
            children: <TemplatePanel scope={scope} variables={catalog} />,
          }))}
        />
      </Card>
    </PageShell>
  );
}
