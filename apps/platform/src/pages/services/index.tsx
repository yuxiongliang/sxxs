import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Spin,
  Statistic,
  Switch,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import PageShell from '@/components/PageShell';
import {
  getPlatformSetting,
  platformSettingImpact,
  savePlatformSetting,
} from '@/services/api';

const CATEGORIES = [
  { key: 'payment', label: '支付', hint: '平台不代收业务款：这里的配置只影响「跟随系统」的租户，支付类配置对租户强制自定义。' },
  { key: 'sms', label: '短信', hint: '平台统一短信通道。租户可跟随，也可用自己申请的服务商账号。' },
  { key: 'email', label: '邮件', hint: '平台统一 SMTP。租户跟随时，发件人显示平台，replyTo 用租户地址。' },
  { key: 'storage', label: '存储', hint: '平台统一存储。切换后历史文件仍可访问（双读兜底）。' },
  { key: 'amap', label: '高德地图', hint: '平台统一 key。注意 Web服务 key 有 QPS 限额，多租户共用需留意。' },
];

const SECRET_HINTS = [
  'password',
  'privatekey',
  'secret',
  'apikey',
  'webkey',
  'accesskeyid',
  'apiv3key',
  'securitycode',
];

function isSecret(key: string): boolean {
  const lower = key.toLowerCase();
  return SECRET_HINTS.some((hint) => lower.includes(hint));
}

/**
 * 按配置结构自动生成表单字段。
 *
 * 手写 5 套分类表单（尤其 payment 里嵌套的 alipay/wechat）维护成本太高，
 * 而配置结构是后端给定的，直接根据值类型渲染即可：
 *   布尔 → Switch、数字 → InputNumber、密钥类 → 密码框、其余 → Input、对象 → 分组递归。
 */
function ConfigFields({
  path,
  value,
}: {
  path: string[];
  value: unknown;
}) {
  const label = path[path.length - 1];
  const name = ['config', ...path];

  if (typeof value === 'boolean') {
    return (
      <Form.Item name={name} label={label} valuePropName="checked">
        <Switch />
      </Form.Item>
    );
  }
  if (typeof value === 'number') {
    return (
      <Form.Item name={name} label={label}>
        <InputNumber style={{ width: 200 }} />
      </Form.Item>
    );
  }
  if (typeof value === 'string') {
    return (
      <Form.Item name={name} label={label}>
        {isSecret(label) ? (
          <Input.Password autoComplete="new-password" placeholder="密钥类字段" />
        ) : (
          <Input allowClear />
        )}
      </Form.Item>
    );
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return (
      <Card size="small" title={label} style={{ marginBottom: 12 }}>
        {Object.entries(value as Record<string, unknown>).map(([key, child]) => (
          <ConfigFields key={key} path={[...path, key]} value={child} />
        ))}
      </Card>
    );
  }
  return (
    <Form.Item name={name} label={label}>
      <Input allowClear />
    </Form.Item>
  );
}

function CategoryPanel({ category }: { category: string }) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const setting = useQuery({
    queryKey: ['platform-setting', category],
    queryFn: () => getPlatformSetting(category),
  });
  const impact = useQuery({
    queryKey: ['platform-setting-impact', category],
    queryFn: () => platformSettingImpact(category),
  });

  const save = useMutation({
    mutationFn: (values: {
      enabled: boolean;
      policy_locked: boolean;
      config: Record<string, unknown>;
    }) =>
      savePlatformSetting(category, {
        enabled: values.enabled,
        policy_locked: values.policy_locked,
        config: values.config ?? {},
      }),
    onSuccess: () => {
      message.success('已保存，跟随系统的租户立即生效');
      queryClient.invalidateQueries({ queryKey: ['platform-setting', category] });
      queryClient.invalidateQueries({
        queryKey: ['platform-setting-impact', category],
      });
    },
    onError: (error: Error) => message.error(error.message),
  });

  if (setting.isLoading || !setting.data) {
    return <Spin />;
  }

  const hint = CATEGORIES.find((item) => item.key === category)?.hint;
  const data = impact.data;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row gutter={[12, 12]}>
        {[
          ['租户总数', data?.tenants_total],
          ['跟随系统', data?.inherit],
          ['自定义', data?.override],
          ['强制跟随', data?.forced],
        ].map(([label, value]) => (
          <Col key={String(label)} xs={12} md={6}>
            <Card size="small">
              <Statistic title={String(label)} value={Number(value ?? 0)} />
            </Card>
          </Col>
        ))}
      </Row>

      {hint ? <Alert type="info" showIcon title={hint} /> : null}

      {!setting.data.enabled ? (
        <Alert
          type="warning"
          showIcon
          title="平台尚未启用该类统一配置"
          description="现在租户即使选择「跟随系统」，也会回落到自己保存的配置。确认字段填好后开启上方开关即可接管。"
        />
      ) : null}

      <Form
        form={form}
        layout="vertical"
        initialValues={{
          enabled: setting.data.enabled,
          policy_locked: Boolean(setting.data.policy_locked),
          config: setting.data.config,
        }}
        onFinish={(values) => save.mutate(values)}
      >
        <Row gutter={24}>
          <Col xs={24} md={6}>
            <Form.Item
              name="enabled"
              label="启用平台统一配置"
              valuePropName="checked"
              extra="启用后，选了「跟随系统」的租户才真正使用这里的值"
            >
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item
              name="policy_locked"
              label="锁定：租户不可自定义"
              valuePropName="checked"
              extra="用于合规要求全站统一的场景"
            >
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item label="配置版本">
              <Space>
                <Tag color="geekblue">v{setting.data.version ?? 1}</Tag>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  后两位：{setting.data.updated_at?.slice(0, 19).replace('T', ' ')}
                </Typography.Text>
              </Space>
            </Form.Item>
          </Col>
        </Row>

        {Object.entries(setting.data.config ?? {}).map(([key, value]) => (
          <ConfigFields key={key} path={[key]} value={value} />
        ))}

        <Button type="primary" htmlType="submit" loading={save.isPending}>
          保存
        </Button>
      </Form>
    </Space>
  );
}

export default function ServicesPage() {
  return (
    <PageShell
      title="服务配置中心"
      subTitle="平台统一配置：租户可选「跟随系统」，也可保留自己的账号"
    >
      <Card>
        <Tabs
          items={CATEGORIES.map((item) => ({
            key: item.key,
            label: item.label,
            children: <CategoryPanel category={item.key} />,
          }))}
        />
      </Card>
    </PageShell>
  );
}
