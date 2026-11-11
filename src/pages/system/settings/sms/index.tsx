import {
  CloudOutlined,
  ExperimentOutlined,
  MessageOutlined,
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
  Statistic,
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
import type { SettingTestResult } from '@/services/system/types';
import SettingPage from '../../components/SettingPage';
import TestResultAlert from '../../components/TestResultAlert';

const REGION_OPTIONS = [
  { label: '华东 1（杭州）', value: 'cn-hangzhou' },
  { label: '华东 2（上海）', value: 'cn-shanghai' },
  { label: '华北 2（北京）', value: 'cn-beijing' },
  { label: '华南 1（深圳）', value: 'cn-shenzhen' },
];

const SmsSettings: React.FC = () => {
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
    queryKey: ['system-setting', 'sms'],
    queryFn: () => getSetting('sms'),
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

  const handleSave = async () => {
    try {
      setSaving(true);
      const payload = await buildPayload();
      await saveSetting('sms', payload);
      message.success('短信设置已保存');
      await queryClient.invalidateQueries({
        queryKey: ['system-setting', 'sms'],
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
      const response = await testSetting('sms', payload.config);
      setResult(response);
      if (response.success) message.success('短信参数校验通过');
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
        title: '短信通道测试',
        channel: 'sms',
        template: values.templateCode,
        audience: 'custom',
        content: `测试短信，验证码 ${values.code}`,
      });
      message.success(`已提交测试短信到 ${values.phone}`);
      setTestOpen(false);
      testForm.resetFields();
    } catch (error: any) {
      message.error(error?.message || '发送失败');
    } finally {
      setSending(false);
    }
  };

  return (
    <SettingPage
      title="短信设置"
      subTitle="阿里云短信服务接入与测试"
      icon={<MessageOutlined />}
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
        description="当前只保存阿里云短信配置并模拟发送结果。真实发送需要 AccessKey、审核通过的签名与模板，并在服务端调用阿里云短信 API。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card
            loading={isLoading}
            title="阿里云短信"
            extra={<Tag color="orange">Aliyun SMS</Tag>}
          >
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                enabled: true,
                provider: 'aliyun',
                region: 'cn-hangzhou',
                dailyLimit: 1000,
              }}
            >
              <Form.Item
                label="启用短信渠道"
                name="enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Form.Item label="服务商" name="provider">
                <Select options={[{ label: '阿里云短信', value: 'aliyun' }]} />
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="AccessKey ID"
                    name="accessKeyId"
                    rules={[{ required: true, message: '请输入 AccessKey ID' }]}
                  >
                    <Input placeholder="LTAI5t..." />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="AccessKey Secret"
                    name="accessKeySecret"
                    rules={[
                      { required: true, message: '请输入 AccessKey Secret' },
                    ]}
                  >
                    <Input.Password placeholder="AccessKey Secret" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="地域" name="region">
                    <Select options={REGION_OPTIONS} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="每日发送上限（条/天）" name="dailyLimit">
                    <InputNumber
                      min={1}
                      max={100000}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="短信签名"
                    name="signName"
                    rules={[{ required: true, message: '请输入短信签名' }]}
                  >
                    <Input placeholder="Ant Design Pro" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="默认模板 Code"
                    name="templateCode"
                    rules={[{ required: true, message: '请输入模板 Code' }]}
                  >
                    <Input placeholder="SMS_000000001" />
                  </Form.Item>
                </Col>
              </Row>
              <Alert
                showIcon
                type="warning"
                title="短信签名和模板必须先在阿里云控制台审核通过，否则 API 会返回失败。"
              />
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Space orientation="vertical" size={16} style={{ display: 'flex' }}>
            <Card title="通道状态">
              <Space
                orientation="vertical"
                size={16}
                style={{ display: 'flex' }}
              >
                <Statistic
                  title="服务商"
                  value="阿里云短信"
                  prefix={<CloudOutlined />}
                />
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="签名">
                    Ant Design Pro
                  </Descriptions.Item>
                  <Descriptions.Item label="模板">
                    SMS_000000001
                  </Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color="success">已配置</Tag>
                  </Descriptions.Item>
                </Descriptions>
              </Space>
            </Card>
            <Card title="发送策略">
              <ul
                style={{
                  paddingLeft: 18,
                  margin: 0,
                  color: '#595959',
                  lineHeight: 1.8,
                }}
              >
                <li>验证码类短信建议 60 秒限流。</li>
                <li>同一手机号每日发送量限制。</li>
                <li>失败记录进入触达通知重试队列。</li>
              </ul>
            </Card>
          </Space>
        </Col>
      </Row>

      <Modal
        title="测试发送短信"
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
          initialValues={{ templateCode: 'SMS_000000001', code: '1234' }}
        >
          <Form.Item
            label="手机号"
            name="phone"
            rules={[
              {
                required: true,
                pattern: /^1\d{10}$/,
                message: '请输入合法手机号',
              },
            ]}
          >
            <Input placeholder="13800000000" />
          </Form.Item>
          <Form.Item
            label="模板 Code"
            name="templateCode"
            rules={[{ required: true, message: '请输入模板 Code' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="验证码"
            name="code"
            rules={[{ required: true, message: '请输入验证码' }]}
          >
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </SettingPage>
  );
};

export default SmsSettings;
