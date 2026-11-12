import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useIntl } from '@umijs/max';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Skeleton,
  Switch,
} from 'antd';
import { useEffect } from 'react';
import PageShell from '@/components/PageShell';
import { getPlatformSetting, savePlatformSetting } from '@/services/api';

interface FormValues {
  name: string;
  shortName: string;
  contactEmail: string;
  supportUrl: string;
  registrationOpen: boolean;
  defaultTrialDays: number;
  announcement: string;
}

const CATEGORY = 'platform';

export default function PlatformSettingsPage() {
  const intl = useIntl();
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['platform-setting', CATEGORY],
    queryFn: () => getPlatformSetting(CATEGORY),
  });

  useEffect(() => {
    if (!data?.config) return;
    const config = data.config as Record<string, unknown>;
    form.setFieldsValue({
      name: String(config.name ?? ''),
      shortName: String(config.shortName ?? ''),
      contactEmail: String(config.contactEmail ?? ''),
      supportUrl: String(config.supportUrl ?? ''),
      registrationOpen: Boolean(config.registrationOpen),
      defaultTrialDays: Number(config.defaultTrialDays ?? 14),
      announcement: String(config.announcement ?? ''),
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      savePlatformSetting(CATEGORY, { enabled: true, config: { ...values } }),
    onSuccess: () => {
      message.success(intl.formatMessage({ id: 'settings.saved' }));
      queryClient.invalidateQueries({ queryKey: ['platform-setting'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  return (
    <PageShell
      title={intl.formatMessage({ id: 'settings.title' })}
      subTitle={intl.formatMessage({ id: 'settings.subtitle' })}
    >
      <Card>
        {isLoading ? (
          <Skeleton active />
        ) : (
          <Form
            form={form}
            layout="vertical"
            onFinish={(values) => save.mutate(values)}
            style={{ maxWidth: 560 }}
          >
            <Form.Item
              name="name"
              label={intl.formatMessage({ id: 'settings.name' })}
              rules={[{ required: true }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="shortName"
              label={intl.formatMessage({ id: 'settings.shortName' })}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="contactEmail"
              label={intl.formatMessage({ id: 'settings.contactEmail' })}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="supportUrl"
              label={intl.formatMessage({ id: 'settings.supportUrl' })}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="registrationOpen"
              label={intl.formatMessage({ id: 'settings.registrationOpen' })}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="defaultTrialDays"
              label={intl.formatMessage({ id: 'settings.defaultTrialDays' })}
            >
              <InputNumber min={0} max={365} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item
              name="announcement"
              label={intl.formatMessage({ id: 'settings.announcement' })}
            >
              <Input.TextArea rows={3} />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={save.isPending}>
              {intl.formatMessage({ id: 'settings.save' })}
            </Button>
          </Form>
        )}
      </Card>
    </PageShell>
  );
}
