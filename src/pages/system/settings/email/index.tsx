import {
  ExperimentOutlined,
  MailOutlined,
  SaveOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Tag,
} from 'antd';
import React, { useEffect, useState } from 'react';
import {
  getSetting,
  saveSetting,
  sendNotification,
  testSetting,
} from '@/services/system/api';
import InheritSwitch, {
  type SettingSource,
} from '@/pages/system/components/InheritSwitch';
import type { SettingTestResult } from '@/services/system/types';
import SettingPage from '../../components/SettingPage';
import TestResultAlert from '../../components/TestResultAlert';

const PROVIDERS = [
  { label: 'QQ 邮箱', value: 'qq', host: 'smtp.qq.com', port: 465, ssl: true },
  {
    label: '163 邮箱',
    value: '163',
    host: 'smtp.163.com',
    port: 465,
    ssl: true,
  },
  {
    label: '企业微信邮箱',
    value: 'exmail',
    host: 'smtp.exmail.qq.com',
    port: 465,
    ssl: true,
  },
  { label: '自定义 SMTP', value: 'custom', host: '', port: 465, ssl: true },
];

const EmailSettings: React.FC = () => {
  const [form] = Form.useForm();
  const [testForm] = Form.useForm();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<SettingTestResult>();
  const [testOpen, setTestOpen] = useState(false);
  const [sending, setSending] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['system-setting', 'email'],
    queryFn: () => getSetting('email'),
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({ enabled: data.enabled, ...data.config });
    }
  }, [data, form]);

  const buildPayload = async () => {
    const values = await form.validateFields();
    const { enabled, ...config } = values;
    return { enabled, config };
  };

  // 来源：本地覆盖优先级高于后端返回（点击后立刻响应，失败则回退）
  const [sourceOverride, setSourceOverride] = useState<SettingSource>();
  const source: SettingSource =
    sourceOverride ?? (data?.source === 'override' ? 'override' : 'inherit');
  const inheriting = source === 'inherit';

  const handleSourceChange = async (next: SettingSource) => {
    setSourceOverride(next);
    try {
      // 不传 config：只切换来源，保留自己已保存的配置
      await saveSetting('email', { source: next, enabled: true });
      await queryClient.invalidateQueries({ queryKey: ['system-setting', 'email'] });
      message.success(next === 'inherit' ? '已切换为跟随系统' : '已切换为自定义');
    } catch (error: any) {
      setSourceOverride(undefined);
      message.error(error?.message || '切换失败');
    }
  };

  const handleSave = async () => {
    if (inheriting) {
      message.info('当前跟随系统，无需保存；如需自定义请先切换到「自定义」');
      return;
    }
    try {
      setSaving(true);
      const payload = await buildPayload();
      await saveSetting('email', { ...payload, source });
      message.success('邮件设置已保存');
      await queryClient.invalidateQueries({
        queryKey: ['system-setting', 'email'],
      });
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    try {
      setTesting(true);
      const payload = await buildPayload();
      const response = await testSetting('email', payload.config);
      setResult(response);
      if (response.success) message.success('SMTP 参数校验通过');
      else message.warning(response.message);
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.message || '测试失败');
    } finally {
      setTesting(false);
    }
  };

  const handleSendTest = async () => {
    const values = await testForm.validateFields();
    try {
      setSending(true);
      await sendNotification({
        title: `邮件测试：${values.subject}`,
        channel: 'email',
        template: 'SMTP_TEST',
        audience: 'custom',
        content: values.content,
      });
      message.success(`测试邮件已提交到 ${values.to}`);
      setTestOpen(false);
      testForm.resetFields();
    } catch (error: any) {
      message.error(error?.message || '发送失败');
    } finally {
      setSending(false);
    }
  };

  const handleProviderChange = (provider: string) => {
    const preset = PROVIDERS.find((item) => item.value === provider);
    if (preset) {
      form.setFieldsValue({
        host: preset.host,
        port: preset.port,
        ssl: preset.ssl,
      });
    }
  };

  return (
    <SettingPage
      title="邮件系统"
      subTitle="通用 SMTP 邮件发送配置"
      icon={<MailOutlined />}
      extra={
        <Space>
          <Button icon={<SendOutlined />} onClick={() => setTestOpen(true)}>
            测试发送
          </Button>
          <Button
            icon={<ExperimentOutlined />}
            loading={testing}
            onClick={handleTest}
          >
            测试连接
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSave}
          >
            保存设置
          </Button>
        </Space>
      }
    >
      <TestResultAlert result={result} />
      <Alert
        showIcon
        type="info"
        title="演示模式"
        description="支持 QQ、163、企业邮箱和自定义 SMTP。真实发信需要邮箱授权码，正式 SaaS 建议使用事务邮件服务并配置 SPF/DKIM/DMARC。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card
            loading={isLoading}
            title="SMTP 配置"
            extra={<Tag color="blue">Transactional Email</Tag>}
          >
            <InheritSwitch
              source={source}
              effectiveSource={data?.effective_source}
              inheritAllowed={data?.inherit_allowed ?? true}
              platformActive={data?.platform_active ?? false}
              policyLocked={data?.policy_locked ?? false}
              maskedFields={data?.masked_fields}
              onChange={handleSourceChange}
            />
            <Form
              disabled={inheriting}
              form={form}
              layout="vertical"
              initialValues={{
                enabled: true,
                provider: 'qq',
                host: 'smtp.qq.com',
                port: 465,
                ssl: true,
                dailyLimit: 500,
              }}
              onValuesChange={(changed) => {
                if (changed.provider) handleProviderChange(changed.provider);
              }}
            >
              <Form.Item
                label="启用邮件渠道"
                name="enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Form.Item label="邮箱服务商" name="provider">
                <Select
                  options={PROVIDERS.map(({ label, value }) => ({
                    label,
                    value,
                  }))}
                />
              </Form.Item>
              <Row gutter={16}>
                <Col span={14}>
                  <Form.Item
                    label="SMTP 主机"
                    name="host"
                    rules={[{ required: true, message: '请输入 SMTP 主机' }]}
                  >
                    <Input placeholder="smtp.qq.com" />
                  </Form.Item>
                </Col>
                <Col span={5}>
                  <Form.Item
                    label="端口"
                    name="port"
                    rules={[{ required: true, message: '请输入端口' }]}
                  >
                    <InputNumber
                      min={1}
                      max={65535}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
                <Col span={5}>
                  <Form.Item label="SSL" name="ssl" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="登录账号"
                    name="username"
                    rules={[{ required: true, message: '请输入登录账号' }]}
                  >
                    <Input placeholder="name@qq.com" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="授权码 / 密码"
                    name="password"
                    rules={[{ required: true, message: '请输入授权码' }]}
                    extra="QQ/163 请使用邮箱设置中生成的 SMTP 授权码"
                  >
                    <Input.Password placeholder="SMTP 授权码" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="发件人名称" name="fromName">
                    <Input placeholder="Ant Design Pro" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="发件人地址"
                    name="fromAddress"
                    rules={[
                      {
                        required: true,
                        type: 'email',
                        message: '请输入合法邮箱',
                      },
                    ]}
                  >
                    <Input placeholder="noreply@example.com" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="每日发送上限（封/天）" name="dailyLimit">
                <InputNumber min={1} max={100000} style={{ width: 220 }} />
              </Form.Item>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Space orientation="vertical" size={16} style={{ display: 'flex' }}>
            <Card title="常用服务商">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="QQ 邮箱">
                  smtp.qq.com:465
                </Descriptions.Item>
                <Descriptions.Item label="163 邮箱">
                  smtp.163.com:465
                </Descriptions.Item>
                <Descriptions.Item label="企业微信">
                  smtp.exmail.qq.com:465
                </Descriptions.Item>
              </Descriptions>
            </Card>
            <Card title="投递率建议">
              <ul
                style={{
                  paddingLeft: 18,
                  margin: 0,
                  color: '#595959',
                  lineHeight: 1.8,
                }}
              >
                <li>生产环境配置 SPF、DKIM、DMARC。</li>
                <li>控制发送频率，处理退信与投诉。</li>
                <li>批量通知建议使用事务邮件服务。</li>
              </ul>
            </Card>
          </Space>
        </Col>
      </Row>

      <Modal
        title="测试发送邮件"
        open={testOpen}
        onCancel={() => setTestOpen(false)}
        onOk={handleSendTest}
        confirmLoading={sending}
        destroyOnHidden
      >
        <Form
          form={testForm}
          layout="vertical"
          style={{ marginTop: 16 }}
          initialValues={{
            subject: 'Ant Design Pro 邮件测试',
            content: '这是一封来自 Ant Design Pro 管理端的测试邮件。',
          }}
        >
          <Form.Item
            label="收件人"
            name="to"
            rules={[
              { required: true, type: 'email', message: '请输入合法邮箱' },
            ]}
          >
            <Input placeholder="receiver@example.com" />
          </Form.Item>
          <Form.Item
            label="主题"
            name="subject"
            rules={[{ required: true, message: '请输入主题' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="正文"
            name="content"
            rules={[{ required: true, message: '请输入正文' }]}
          >
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </SettingPage>
  );
};

export default EmailSettings;
