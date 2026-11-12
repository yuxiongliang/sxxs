import { useQuery } from '@tanstack/react-query';
import { useIntl } from '@umijs/max';
import { Col, Empty, Row, Spin } from 'antd';
import { listPublicProducts } from '@/services/commerce/api';
import useStyles from '@/pages/site/style';
import MallShell from './components/MallShell';
import ProductCard from './components/ProductCard';

/**
 * 商品首页（站点前台，公开浏览）。
 *
 * 数据来自公开接口 `/api/v1/public/products`（匿名可读、字段白名单），
 * 与登录态无关；加购/下单由卡片内部引导登录。
 */
export default function ProductsPage() {
  const { styles } = useStyles();
  const { formatMessage: t } = useIntl();
  const productsQuery = useQuery({
    queryKey: ['public-products'],
    queryFn: () => listPublicProducts({ limit: 48 }),
    staleTime: 60_000,
  });
  const products = productsQuery.data ?? [];

  return (
    <MallShell activeKey="products">
      <section className={styles.section}>
        <div className={styles.container}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>
              {t({ id: 'mall.products.title', defaultMessage: '商品' })}
            </h2>
            <p className={styles.sectionSubtitle}>
              {t(
                {
                  id: 'mall.products.subtitle',
                  defaultMessage: '卖家发布的在售商品，共 {count} 件',
                },
                { count: products.length },
              )}
            </p>
          </div>

          {productsQuery.isLoading ? (
            <div style={{ padding: 64, textAlign: 'center' }}>
              <Spin />
            </div>
          ) : productsQuery.isError ? (
            <Empty
              description={t({
                id: 'mall.products.error',
                defaultMessage: '商品加载失败，请稍后重试',
              })}
            />
          ) : products.length === 0 ? (
            <Empty
              description={t({
                id: 'mall.products.empty',
                defaultMessage: '暂时还没有在售商品',
              })}
            />
          ) : (
            <Row gutter={[16, 16]}>
              {products.map((item) => (
                <Col xs={24} sm={12} md={8} xl={6} key={item.id}>
                  <ProductCard product={item} />
                </Col>
              ))}
            </Row>
          )}
        </div>
      </section>
    </MallShell>
  );
}
