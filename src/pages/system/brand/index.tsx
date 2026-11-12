import { PictureOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Col,
  Form,
  Input,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import SettingPage from '@/pages/system/components/SettingPage';
import { getTenantBrand, saveTenantBrand } from '@/services/system/api';

interface FormValues {
  display_name: string;
  logo_url: string;
  favicon_url: string;
  theme_color: string;
}

export default function TenantBrandPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const queryClient = useQueryClient();

  const brand = useQuery({
    queryKey: ['tenant-brand'],
    queryFn: getTenantBrand,
  });

  const save = useMutation({
    mutationFn: (values: FormValues) => saveTenantBrand(values),
    onSuccess: () => {
      message.success('品牌已保存，站点标题与 logo 立即生效');
      queryClient.invalidateQueries({ queryKey: ['tenant-brand'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  if (brand.isLoading || !brand.data) return <Spin />;

  const current = brand.data;

  return (
    <SettingPage
      title="站点品牌"
      subTitle="买家看到的全站名称与 logo；通知模板里的 {{tenant_name}} 也取这里"
      icon={<PictureOutlined />}
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={13}>
          <Card>
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                display_name: current.display_name,
                logo_url: current.logo_url ?? '',
                favicon_url: current.favicon_url ?? '',
                theme_color: current.theme_color ?? '',
              }}
              onFinish={(values) => save.mutate(values)}
            >
              <Form.Item
                name="display_name"
                label="全站名称"
                extra="为空时回落到租户名称，不会显示空白"
              >
                <Input placeholder="例如 李思的二手好物" allowClear />
              </Form.Item>
              <Form.Item
                name="logo_url"
                label="Logo 地址"
                extra="建议用附件中心上传后复制公开直链（/api/v1/attachments/public/{id}）"
              >
                <Input placeholder="/api/v1/attachments/public/12" allowClear />
              </Form.Item>
              <Form.Item name="favicon_url" label="Favicon 地址">
                <Input placeholder="留空则用默认图标" allowClear />
              </Form.Item>
              <Form.Item
                name="theme_color"
                label="主题色"
                extra="形如 #722ed1；留空用默认主题"
              >
                <Input placeholder="#722ed1" allowClear />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={save.isPending}>
                保存
              </Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={11}>
          <Card title="预览">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Space align="center">
                {current.logo_url ? (
                  <img
                    src={current.logo_url}
                    alt="logo"
                    style={{ width: 40, height: 40, objectFit: 'contain' }}
                  />
                ) : (
                  <Tag color="default">未设置 logo</Tag>
                )}
                <Typography.Text strong style={{ fontSize: 18 }}>
                  {current.display_name}
                </Typography.Text>
              </Space>
              <Typography.Text type="secondary">
                租户标识：{current.slug}（对外展示用 display_name，slug
                只在内部使用）
              </Typography.Text>
              {current.theme_color ? (
                <Space>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 18,
                      height: 18,
                      borderRadius: 4,
                      background: current.theme_color,
                    }}
                  />
                  <Typography.Text>{current.theme_color}</Typography.Text>
                </Space>
              ) : null}
            </Space>
          </Card>
        </Col>
      </Row>
    </SettingPage>
  );
}
