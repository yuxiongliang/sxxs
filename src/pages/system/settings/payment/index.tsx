import {
  AlipayCircleOutlined,
  CheckCircleOutlined,
  ExperimentOutlined,
  QrcodeOutlined,
  SaveOutlined,
  SafetyCertificateOutlined,
  WechatOutlined,
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
  Modal,
  QRCode,
  Row,
  Segmented,
  Space,
  Switch,
  Tabs,
  Tag,
} from 'antd';
import React, { useEffect, useState } from 'react';
import { getSetting, saveSetting, testSetting } from '@/services/system/api';
import type { SettingTestResult } from '@/services/system/types';
import SettingPage from '../../components/SettingPage';
import TestResultAlert from '../../components/TestResultAlert';

const PaymentSettings: React.FC = () => {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<SettingTestResult>();
  const [qrOpen, setQrOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['system-setting', 'payment'],
    queryFn: () => getSetting('payment'),
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        enabled: data.enabled,
        alipay: data.config.alipay,
        wechat: data.config.wechat,
      });
    }
  }, [data, form]);

  const buildPayload = async () => {
    const values = await form.validateFields();
    return {
      enabled: values.enabled,
      config: { alipay: values.alipay, wechat: values.wechat },
    };
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const payload = await buildPayload();
      await saveSetting('payment', payload);
      message.success('支付设置已保存');
      await queryClient.invalidateQueries({
        queryKey: ['system-setting', 'payment'],
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
      const response = await testSetting('payment', payload.config);
      setResult(response);
      if (response.success) message.success('支付参数校验通过');
      else message.warning(response.message);
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.message || '测试失败');
    } finally {
      setTesting(false);
    }
  };

  return (
    <SettingPage
      title="支付设置"
      subTitle="接入支付宝与微信支付官方组件"
      icon={<SafetyCertificateOutlined />}
      extra={
        <Space>
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
        description="当前保存的是支付网关配置，测试连接与二维码为本地模拟结果。真实收款需要服务端接入支付宝/微信官方 SDK、商户证书和异步回调验签。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card
            loading={isLoading}
            title="支付渠道配置"
            extra={<Tag color="blue">官方组件接入</Tag>}
          >
            <Form
              form={form}
              layout="vertical"
              initialValues={{ enabled: true }}
            >
              <Form.Item
                label="启用支付模块"
                name="enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Tabs
                items={[
                  {
                    key: 'alipay',
                    forceRender: true,
                    label: (
                      <Space>
                        <AlipayCircleOutlined style={{ color: '#1677ff' }} />
                        支付宝
                      </Space>
                    ),
                    children: (
                      <>
                        <Form.Item
                          label="启用支付宝"
                          name={['alipay', 'enabled']}
                          valuePropName="checked"
                        >
                          <Switch />
                        </Form.Item>
                        <Form.Item
                          label="运行环境"
                          name={['alipay', 'environment']}
                        >
                          <Segmented
                            options={[
                              { label: '沙箱环境', value: 'sandbox' },
                              { label: '生产环境', value: 'production' },
                            ]}
                          />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item
                              label="App ID"
                              name={['alipay', 'appId']}
                              rules={[
                                {
                                  required: true,
                                  message: '请输入支付宝 App ID',
                                },
                              ]}
                            >
                              <Input placeholder="2021000000000000" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item
                              label="商户号"
                              name={['alipay', 'merchantId']}
                            >
                              <Input placeholder="2088000000000000" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Form.Item
                          label="应用私钥"
                          name={['alipay', 'privateKey']}
                          extra="仅保存在后端，前端不会持久化明文；生产环境请使用 KMS/Vault。"
                        >
                          <Input.TextArea
                            rows={3}
                            placeholder="-----BEGIN PRIVATE KEY-----"
                          />
                        </Form.Item>
                        <Form.Item
                          label="支付宝公钥"
                          name={['alipay', 'publicKey']}
                        >
                          <Input.TextArea
                            rows={3}
                            placeholder="-----BEGIN PUBLIC KEY-----"
                          />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item
                              label="异步通知地址"
                              name={['alipay', 'notifyUrl']}
                            >
                              <Input placeholder="https://api.example.com/api/v1/payments/alipay/notify" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item
                              label="同步返回地址"
                              name={['alipay', 'returnUrl']}
                            >
                              <Input placeholder="https://admin.example.com/payment/result" />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    ),
                  },
                  {
                    key: 'wechat',
                    forceRender: true,
                    label: (
                      <Space>
                        <WechatOutlined style={{ color: '#07c160' }} />
                        微信支付
                      </Space>
                    ),
                    children: (
                      <>
                        <Form.Item
                          label="启用微信支付"
                          name={['wechat', 'enabled']}
                          valuePropName="checked"
                        >
                          <Switch />
                        </Form.Item>
                        <Form.Item
                          label="运行环境"
                          name={['wechat', 'environment']}
                        >
                          <Segmented
                            options={[
                              { label: '沙箱环境', value: 'sandbox' },
                              { label: '生产环境', value: 'production' },
                            ]}
                          />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item
                              label="App ID"
                              name={['wechat', 'appId']}
                              rules={[
                                {
                                  required: true,
                                  message: '请输入微信 App ID',
                                },
                              ]}
                            >
                              <Input placeholder="wx0000000000000000" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item
                              label="商户号"
                              name={['wechat', 'mchId']}
                            >
                              <Input placeholder="1600000000" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item
                              label="API v3 密钥"
                              name={['wechat', 'apiV3Key']}
                            >
                              <Input.Password placeholder="32 位 API v3 密钥" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item
                              label="证书序列号"
                              name={['wechat', 'serialNo']}
                            >
                              <Input placeholder="商户 API 证书序列号" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Form.Item
                          label="商户私钥"
                          name={['wechat', 'privateKey']}
                        >
                          <Input.TextArea
                            rows={3}
                            placeholder="apiclient_key.pem 内容"
                          />
                        </Form.Item>
                        <Form.Item
                          label="支付回调地址"
                          name={['wechat', 'notifyUrl']}
                        >
                          <Input placeholder="https://api.example.com/api/v1/payments/wechat/notify" />
                        </Form.Item>
                      </>
                    ),
                  },
                ]}
              />
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Space orientation="vertical" size={16} style={{ display: 'flex' }}>
            <Card title="接入状态">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="支付宝">
                  <Tag icon={<CheckCircleOutlined />} color="success">
                    已配置
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="微信支付">
                  <Tag icon={<CheckCircleOutlined />} color="success">
                    已配置
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="回调验签">
                  <Tag color="gold">待服务端实现</Tag>
                </Descriptions.Item>
              </Descriptions>
            </Card>
            <Card
              title="官方组件"
              extra={
                <Button
                  type="link"
                  icon={<QrcodeOutlined />}
                  onClick={() => setQrOpen(true)}
                >
                  测试二维码
                </Button>
              }
            >
              <Space
                orientation="vertical"
                size={12}
                style={{ display: 'flex' }}
              >
                <Alert
                  showIcon
                  type="info"
                  title="支付宝"
                  description="Alipay Global / 手机网站支付 / 当面付"
                />
                <Alert
                  showIcon
                  type="success"
                  title="微信支付"
                  description="JSAPI / Native / H5 支付"
                />
              </Space>
            </Card>
            <Card title="安全提示">
              <ul
                style={{
                  paddingLeft: 18,
                  margin: 0,
                  color: '#595959',
                  lineHeight: 1.8,
                }}
              >
                <li>商户私钥只允许保存在服务端。</li>
                <li>回调必须验签并做幂等处理。</li>
                <li>生产环境请使用 KMS/Vault 管理密钥。</li>
              </ul>
            </Card>
          </Space>
        </Col>
      </Row>

      <Modal
        title="测试支付二维码"
        open={qrOpen}
        footer={null}
        onCancel={() => setQrOpen(false)}
        destroyOnHidden
      >
        <div style={{ textAlign: 'center', padding: 24 }}>
          <QRCode
            value={
              result?.qr_code || 'https://qr.alipay.com/ant-design-pro-demo'
            }
            size={220}
          />
          <p style={{ marginTop: 16, color: '#8c8c8c' }}>
            演示二维码，不会发起真实扣款。
          </p>
        </div>
      </Modal>
    </SettingPage>
  );
};

export default PaymentSettings;
