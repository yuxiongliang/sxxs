import {
  CloudServerOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  SaveOutlined,
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
  Row,
  Segmented,
  Space,
  Statistic,
  Switch,
  Tag,
} from 'antd';
import React, { useEffect, useState } from 'react';
import {
  getAttachmentStats,
  getSetting,
  saveSetting,
  testSetting,
} from '@/services/system/api';
import type { SettingTestResult } from '@/services/system/types';
import SettingPage from '../../components/SettingPage';
import TestResultAlert from '../../components/TestResultAlert';
import { formatBytes } from '../../utils';

const StorageSettings: React.FC = () => {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<SettingTestResult>();
  const driver = Form.useWatch('driver', form);

  const { data, isLoading } = useQuery({
    queryKey: ['system-setting', 'storage'],
    queryFn: () => getSetting('storage'),
  });
  const { data: stats } = useQuery({
    queryKey: ['attachment-stats'],
    queryFn: getAttachmentStats,
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
      await saveSetting('storage', payload);
      message.success('存储设置已保存');
      await queryClient.invalidateQueries({
        queryKey: ['system-setting', 'storage'],
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
      const response = await testSetting('storage', payload.config);
      setResult(response);
      if (response.success) message.success('存储配置校验通过');
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
      title="存储设置"
      subTitle="本地存储与阿里云 OSS 存储切换"
      icon={<CloudServerOutlined />}
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
        description="本地存储会真实写入 backend/uploads；OSS 配置只做参数校验，真实上传需要配置 Bucket、AccessKey 并接入阿里云 OSS SDK。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card
            loading={isLoading}
            title="存储驱动"
            extra={<Tag color="blue">Storage Adapter</Tag>}
          >
            <Form
              form={form}
              layout="vertical"
              initialValues={{ enabled: true, driver: 'local' }}
            >
              <Form.Item
                label="启用文件存储"
                name="enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Form.Item label="存储位置" name="driver">
                <Segmented
                  options={[
                    { label: '本地存储', value: 'local' },
                    { label: '阿里云 OSS', value: 'oss' },
                  ]}
                />
              </Form.Item>

              {driver !== 'oss' ? (
                <Card
                  size="small"
                  title="本地存储配置"
                  style={{ marginBottom: 16 }}
                >
                  <Form.Item
                    label="上传目录"
                    name={['local', 'uploadDir']}
                    rules={[{ required: true, message: '请输入上传目录' }]}
                  >
                    <Input placeholder="./uploads" />
                  </Form.Item>
                  <Form.Item
                    label="公开访问地址"
                    name={['local', 'publicBaseUrl']}
                    rules={[{ required: true, message: '请输入公开访问地址' }]}
                  >
                    <Input placeholder="http://127.0.0.1:9000/uploads" />
                  </Form.Item>
                  <Alert
                    showIcon
                    type="success"
                    title="本地存储适合开发和单机部署，生产环境建议切换到 OSS。"
                  />
                </Card>
              ) : (
                <Card
                  size="small"
                  title="阿里云 OSS 配置"
                  style={{ marginBottom: 16 }}
                >
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        label="Endpoint"
                        name={['oss', 'endpoint']}
                        rules={[{ required: true, message: '请输入 Endpoint' }]}
                      >
                        <Input placeholder="oss-cn-hangzhou.aliyuncs.com" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        label="Bucket"
                        name={['oss', 'bucket']}
                        rules={[{ required: true, message: '请输入 Bucket' }]}
                      >
                        <Input placeholder="my-bucket" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        label="AccessKey ID"
                        name={['oss', 'accessKeyId']}
                        rules={[
                          { required: true, message: '请输入 AccessKey ID' },
                        ]}
                      >
                        <Input placeholder="LTAI5t..." />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        label="AccessKey Secret"
                        name={['oss', 'accessKeySecret']}
                        rules={[
                          {
                            required: true,
                            message: '请输入 AccessKey Secret',
                          },
                        ]}
                      >
                        <Input.Password placeholder="AccessKey Secret" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="自定义域名" name={['oss', 'domain']}>
                        <Input placeholder="https://cdn.example.com" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="路径前缀" name={['oss', 'prefix']}>
                        <Input placeholder="uploads/" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Alert
                    showIcon
                    type="warning"
                    title="建议使用 STS 临时凭证 + 私有 Bucket + 签名 URL，不要把长期 AccessKey 写进前端。"
                  />
                </Card>
              )}
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Space orientation="vertical" size={16} style={{ display: 'flex' }}>
            <Card title="当前存储">
              <Statistic
                title="驱动"
                value={driver === 'oss' ? '阿里云 OSS' : '本地存储'}
                prefix={<DatabaseOutlined />}
              />
              <Descriptions column={1} size="small" style={{ marginTop: 16 }}>
                <Descriptions.Item label="附件总数">
                  {stats?.total ?? 0} 个
                </Descriptions.Item>
                <Descriptions.Item label="占用空间">
                  {formatBytes(stats?.totalSize ?? 0)}
                </Descriptions.Item>
                <Descriptions.Item label="图片 / 文档">
                  {stats?.images ?? 0} / {stats?.documents ?? 0}
                </Descriptions.Item>
              </Descriptions>
            </Card>
            <Card title="存储策略">
              <ul
                style={{
                  paddingLeft: 18,
                  margin: 0,
                  color: '#595959',
                  lineHeight: 1.8,
                }}
              >
                <li>附件元数据存 PostgreSQL，文件存本地或 OSS。</li>
                <li>生产环境使用私有 Bucket + 签名 URL。</li>
                <li>上传前做 MIME 校验、大小限制和病毒扫描。</li>
              </ul>
            </Card>
          </Space>
        </Col>
      </Row>
    </SettingPage>
  );
};

export default StorageSettings;
