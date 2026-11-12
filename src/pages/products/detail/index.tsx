import { ShoppingOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useIntl, useNavigate, useParams } from '@umijs/max';
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
import { useMemo, useState } from 'react';
import { addCartItem, getPublicProductDetail } from '@/services/commerce/api';
import useStyles from '@/pages/site/style';
import MallShell from '../components/MallShell';

const yuan = (cents: number) => `¥${(cents / 100).toFixed(2)}`;

/**
 * 商品详情（站点前台，公开浏览）。
 *
 * 从原 `/portal/products/:id` 迁出：浏览不需要登录，
 * 只有「加入购物车 / 立即购买」需要，未登录时引导登录并回到本页。
 */
export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const productId = Number(id);
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { styles } = useStyles();
  const { formatMessage: t } = useIntl();

  const [skuId, setSkuId] = useState<number>();
  const [quantity, setQuantity] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-product-detail', productId],
    queryFn: () => getPublicProductDetail(productId),
    enabled: Number.isFinite(productId),
  });

  const activeSku = useMemo(() => {
    if (!data?.skus?.length) return data?.sku ?? undefined;
    return data.skus.find((item) => item.id === skuId) ?? data.skus[0];
  }, [data, skuId]);

  const loginPath = `/user/login?redirect=${encodeURIComponent(`/products/${productId}`)}`;

  const requireLogin = async () => {
    try {
      // 用一个轻量鉴权探测判断登录态：未登录时 queryMe 会 401 并被拦截器带到这里
      const { me } = await import('@/services/auth/api');
      await me();
      return true;
    } catch {
      window.location.assign(loginPath);
      return false;
    }
  };

  const addToCart = async () => {
    if (!activeSku) return;
    if (!(await requireLogin())) return;
    try {
      await addCartItem({ sku_id: activeSku.id, quantity });
      message.success(
        t({ id: 'product.detail.addedCart', defaultMessage: '已加入购物车' }),
      );
    } catch (error) {
      message.error((error as Error)?.message || '加入购物车失败');
    }
  };

  const buyNow = async () => {
    if (!activeSku) return;
    if (!(await requireLogin())) return;
    try {
      await addCartItem({ sku_id: activeSku.id, quantity });
      navigate('/portal/cart');
    } catch (error) {
      message.error((error as Error)?.message || '下单失败');
    }
  };

  const outOfStock = (activeSku?.stock ?? 0) <= 0;

  return (
    <MallShell activeKey="products">
      <section className={styles.section}>
        <div className={styles.container}>
          {isLoading ? (
            <Card>
              <Skeleton active />
            </Card>
          ) : isError || !data ? (
            <Empty
              description={t({
                id: 'product.detail.notFound',
                defaultMessage: '商品不存在或已下架',
              })}
            />
          ) : (
            <Row gutter={[24, 24]}>
              <Col xs={24} md={10}>
                <Card
                  styles={{ body: { padding: 0 } }}
                  cover={
                    data.main_image ? (
                      <img
                        src={data.main_image}
                        alt={data.name}
                        style={{
                          width: '100%',
                          height: 320,
                          objectFit: 'cover',
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          height: 320,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 72,
                          color: 'var(--ant-color-primary)',
                          background:
                            'linear-gradient(135deg, var(--ant-color-primary-bg), var(--ant-color-fill-secondary))',
                        }}
                      >
                        <ShoppingOutlined />
                      </div>
                    )
                  }
                />
              </Col>
              <Col xs={24} md={14}>
                <Card>
                  <Typography.Title level={3} style={{ marginTop: 0 }}>
                    {data.name}
                  </Typography.Title>
                  <Space
                    orientation="vertical"
                    size={14}
                    style={{ width: '100%' }}
                  >
                    <Typography.Text type="secondary">
                      {data.subtitle || '—'}
                    </Typography.Text>

                    <div
                      style={{
                        color: 'var(--ant-color-error)',
                        fontSize: 28,
                        fontWeight: 700,
                      }}
                    >
                      {yuan(activeSku?.price_cents ?? 0)}
                    </div>

                    <Space size={8} wrap>
                      <Tag color="blue">
                        {t({
                          id: 'product.detail.seller',
                          defaultMessage: '卖家',
                        })}
                        ：{data.seller_name || '-'}
                      </Tag>
                      <Tag>
                        {t({
                          id: 'product.detail.shop',
                          defaultMessage: '店铺',
                        })}
                        ：{data.shop_name || '-'}
                      </Tag>
                      <Tag color={outOfStock ? 'red' : 'green'}>
                        {t(
                          {
                            id: 'mall.product.stock',
                            defaultMessage: '库存 {count}',
                          },
                          { count: activeSku?.stock ?? 0 },
                        )}
                      </Tag>
                    </Space>

                    {(data.skus?.length ?? 0) > 1 ? (
                      <Space size={8} wrap>
                        <Typography.Text>
                          {t({
                            id: 'product.detail.spec',
                            defaultMessage: '规格',
                          })}
                          ：
                        </Typography.Text>
                        {(data.skus ?? []).map((sku) => (
                          <Button
                            key={sku.id}
                            type={
                              activeSku?.id === sku.id ? 'primary' : 'default'
                            }
                            onClick={() => setSkuId(sku.id)}
                          >
                            {sku.name}
                          </Button>
                        ))}
                      </Space>
                    ) : null}

                    <Space size={8}>
                      <Typography.Text>
                        {t({
                          id: 'product.detail.quantity',
                          defaultMessage: '数量',
                        })}
                        ：
                      </Typography.Text>
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
                        {t({
                          id: 'product.detail.buyNow',
                          defaultMessage: '立即购买',
                        })}
                      </Button>
                      <Button
                        size="large"
                        disabled={outOfStock}
                        onClick={addToCart}
                      >
                        {t({
                          id: 'product.detail.addCart',
                          defaultMessage: '加入购物车',
                        })}
                      </Button>
                    </Space>

                    <Typography.Paragraph
                      type="secondary"
                      style={{ marginTop: 8 }}
                    >
                      {t({
                        id: 'product.detail.noDescription',
                        defaultMessage: '卖家暂未填写商品描述。',
                      })}
                    </Typography.Paragraph>
                  </Space>
                </Card>
              </Col>
            </Row>
          )}
        </div>
      </section>
    </MallShell>
  );
}
