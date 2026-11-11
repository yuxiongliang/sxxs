import { ShoppingCartOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from '@umijs/max';
import {
  App,
  Button,
  Card,
  Col,
  Empty,
  InputNumber,
  Row,
  Skeleton,
  Space,
  Tag,
  Typography,
} from 'antd';
import React, { useMemo, useState } from 'react';
import { addCartItem, getPortalProductDetail } from '@/services/commerce/api';
import PortalShell from '../components/PortalShell';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

const ProductDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const productId = Number(id);
  const { message } = App.useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [skuId, setSkuId] = useState<number>();
  const [quantity, setQuantity] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['portal-product-detail', productId],
    queryFn: () => getPortalProductDetail(productId),
    enabled: Number.isFinite(productId),
  });

  const activeSku = useMemo(() => {
    if (!data?.skus?.length) return undefined;
    return data.skus.find((item) => item.id === skuId) ?? data.skus[0];
  }, [data, skuId]);

  const addToCart = async () => {
    if (!activeSku) return;
    await addCartItem({ sku_id: activeSku.id, quantity });
    message.success('已加入购物车');
    await queryClient.invalidateQueries({ queryKey: ['portal-cart'] });
  };

  const buyNow = async () => {
    await addToCart();
    navigate('/portal/cart');
  };

  if (isLoading) {
    return (
      <PortalShell title="商品详情">
        <Card>
          <Skeleton active />
        </Card>
      </PortalShell>
    );
  }

  if (!data) {
    return (
      <PortalShell title="商品详情">
        <Card>
          <Empty description="商品不存在或已下架" />
        </Card>
      </PortalShell>
    );
  }

  const outOfStock = (activeSku?.stock ?? 0) <= 0;

  return (
    <PortalShell title="商品详情">
      <Row gutter={24}>
        <Col xs={24} md={10}>
          <Card
            cover={
              <div
                style={{
                  height: 320,
                  background: 'linear-gradient(135deg,#e6f4ff,#bae0ff)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 72,
                  color: '#1677ff',
                }}
              >
                <ShoppingCartOutlined />
              </div>
            }
          />
        </Col>
        <Col xs={24} md={14}>
          <Card>
            <Typography.Title level={3} style={{ marginTop: 0 }}>
              {data.name}
            </Typography.Title>
            <Space orientation="vertical" size={12} style={{ width: '100%' }}>
              <Typography.Text type="secondary">
                {data.subtitle || '-'}
              </Typography.Text>
              <div style={{ color: '#ff4d4f', fontSize: 28, fontWeight: 600 }}>
                {yuan(activeSku?.price_cents ?? 0)}
              </div>
              <Space size={8} wrap>
                <Tag color="blue">
                  卖家：{data.seller_name || `#${data.seller_id}`}
                </Tag>
                <Tag>店铺：{data.shop_name || `#${data.shop_id}`}</Tag>
                <Tag color={outOfStock ? 'red' : 'green'}>
                  库存 {activeSku?.stock ?? 0}
                </Tag>
              </Space>

              {data.skus.length > 1 ? (
                <Space size={8} wrap>
                  <Typography.Text>规格：</Typography.Text>
                  {data.skus.map((sku) => (
                    <Button
                      key={sku.id}
                      type={activeSku?.id === sku.id ? 'primary' : 'default'}
                      onClick={() => setSkuId(sku.id)}
                    >
                      {sku.name}
                    </Button>
                  ))}
                </Space>
              ) : null}

              <Space size={8}>
                <Typography.Text>数量：</Typography.Text>
                <InputNumber
                  min={1}
                  max={Math.max(1, activeSku?.stock ?? 1)}
                  value={quantity}
                  onChange={(value) => setQuantity(value ?? 1)}
                />
              </Space>

              <Space size={12}>
                <Button
                  type="primary"
                  size="large"
                  disabled={outOfStock}
                  onClick={buyNow}
                >
                  立即购买
                </Button>
                <Button size="large" disabled={outOfStock} onClick={addToCart}>
                  加入购物车
                </Button>
              </Space>

              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                {data.description || '卖家暂未填写商品描述。'}
              </Typography.Paragraph>
            </Space>
          </Card>
        </Col>
      </Row>
    </PortalShell>
  );
};

export default ProductDetailPage;
