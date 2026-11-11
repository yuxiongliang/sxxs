import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { useState } from 'react';
import AMapView from '@/components/AMapView';
import {
  type AMapRegeo,
  type AMapSettingConfig,
  getAMapFrontendConfig,
  getAMapSetting,
  regeo,
  saveAMapSetting,
  testAMapConnection,
} from '@/services/amap/api';

const { Text, Paragraph } = Typography;

export default function AMapSettingPage() {
  const [form] = Form.useForm<AMapSettingConfig>();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [notice, setNotice] = useState<{
    type: 'success' | 'error' | 'info';
    text: string;
  } | null>(null);
  const [picked, setPicked] = useState<AMapRegeo | null>(null);

  const settingQuery = useQuery({
    queryKey: ['amap-setting'],
    queryFn: getAMapSetting,
  });
  const mapConfigQuery = useQuery({
    queryKey: ['amap-frontend-config'],
    queryFn: getAMapFrontendConfig,
    retry: false,
  });

  const initialValues = settingQuery.data?.config;

  const handleSave = async (values: AMapSettingConfig) => {
    setSaving(true);
    try {
      await saveAMapSetting({
        ...values,
        enabled: form.getFieldValue('enabled') ?? true,
      });
      setNotice({ type: 'success', text: '配置已保存' });
      await queryClient.invalidateQueries({
        queryKey: ['amap-frontend-config'],
      });
      await queryClient.invalidateQueries({ queryKey: ['amap-setting'] });
    } catch (error) {
      setNotice({ type: 'error', text: (error as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await testAMapConnection();
      setNotice({
        type: result.success ? 'success' : 'error',
        text: result.message,
      });
    } catch (error) {
      setNotice({ type: 'error', text: (error as Error).message });
    } finally {
      setTesting(false);
    }
  };

  const handlePick = async (lng: number, lat: number) => {
    try {
      const result = await regeo(lng, lat);
      setPicked(result);
    } catch (error) {
      setNotice({ type: 'error', text: (error as Error).message });
    }
  };

  const mapConfig = mapConfigQuery.data;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={12}>
        <Card title="接入配置" loading={settingQuery.isLoading}>
          {notice ? (
            <Alert
              style={{ marginBottom: 16 }}
              type={notice.type}
              showIcon
              title={notice.text}
            />
          ) : null}
          <Form
            form={form}
            layout="vertical"
            initialValues={initialValues}
            onFinish={handleSave}
          >
            <Form.Item
              name="enabled"
              label="启用高德地图"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="jsKey"
              label="Web端(JS API) key"
              extra="用于前端交互地图，需要在控制台配置域名白名单"
            >
              <Input placeholder="例如 1a2b3c4d5e6f7g8h9i0j" allowClear />
            </Form.Item>
            <Form.Item
              name="webKey"
              label="Web服务 key"
              extra="只用于后端调 REST（逆地理编码/静态地图），不会下发到浏览器。与 JS API key 不能混用，否则报 10009"
            >
              <Input.Password placeholder="Web服务 key" />
            </Form.Item>
            <Form.Item
              name="securityCode"
              label="安全密钥 securityJsCode"
              extra="2021-12-02 之后申请的 key 必填；开启下方代理时不会下发到浏览器"
            >
              <Input.Password placeholder="安全密钥" />
            </Form.Item>
            <Form.Item
              name="useProxy"
              label="安全密钥走服务端代理（推荐）"
              valuePropName="checked"
              extra="开启后前端只拿到 serviceHost（/_AMapService），安全密钥留在服务端"
            >
              <Switch />
            </Form.Item>
            <Form.Item name="defaultCenter" label="默认中心点（经度,纬度）">
              <Input placeholder="116.397428,39.90923" />
            </Form.Item>
            <Form.Item name="defaultZoom" label="默认缩放级别（3-18）">
              <InputNumber min={3} max={18} style={{ width: 160 }} />
            </Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存
              </Button>
              <Button onClick={handleTest} loading={testing}>
                测试连接
              </Button>
            </Space>
          </Form>
        </Card>
      </Col>

      <Col xs={24} xl={12}>
        <Card
          title="地图预览"
          extra={
            mapConfig?.useProxy ? (
              <Tag color="green">安全密钥：服务端代理</Tag>
            ) : (
              <Tag color="orange">安全密钥：明文（不建议生产）</Tag>
            )
          }
        >
          {mapConfig?.jsKey ? (
            <>
              <AMapView config={mapConfig} height={360} onPick={handlePick} />
              <Paragraph type="secondary" style={{ marginTop: 12 }}>
                点击地图任意位置会调用后端逆地理编码接口（走 Web服务 key）。
              </Paragraph>
              {picked ? (
                <Alert
                  type="info"
                  showIcon
                  title={picked.formatted_address || '未解析出地址'}
                  description={`省市区：${picked.province || '—'} / ${picked.city || '—'} / ${picked.district || '—'}　adcode：${picked.adcode || '—'}`}
                />
              ) : (
                <Text type="secondary">尚未选点</Text>
              )}
            </>
          ) : (
            <Alert
              type="warning"
              showIcon
              title="还没有可用的 JS API key"
              description="先在左侧填写 Web端(JS API) key 并保存，地图即可加载。"
            />
          )}
        </Card>
      </Col>
    </Row>
  );
}
