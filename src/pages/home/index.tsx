import { ArrowRightOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useIntl } from '@umijs/max';
import { Button, Col, Row } from 'antd';
import MallShell from '@/pages/products/components/MallShell';
import HeroBackdrop from '@/pages/site/components/HeroBackdrop';
import useStyles from '@/pages/site/style';
import { usePrefersReducedMotion } from '@/pages/site/useReducedMotion';
import { useTypewriter } from '@/pages/site/useTypewriter';
import { listPublicProducts } from '@/services/commerce/api';

/**
 * 站点首页（商城前台）。
 *
 * 只保留 Hero 与两项指标；商品浏览已迁到独立的 `/products` 商品首页，
 * 导航、页脚、主题、搜索统一由 MallShell 提供。
 */
export default function MallHomePage() {
  const { styles } = useStyles();
  const { formatMessage: t } = useIntl();
  const reducedMotion = usePrefersReducedMotion();

  const title = t({ id: 'mall.hero.title', defaultMessage: '交易Hub中心' });
  const { visible: typedTitle, blinking } = useTypewriter(title, reducedMotion);

  const productsQuery = useQuery({
    queryKey: ['public-products'],
    queryFn: () => listPublicProducts({ limit: 48 }),
    staleTime: 60_000,
  });
  const products = productsQuery.data ?? [];
  const shopCount = new Set(products.map((item) => item.shop_id)).size;

  return (
    <MallShell activeKey="home">
      <section className={styles.hero} id="mall-top">
        <HeroBackdrop className={styles.heroBackdrop} />
        <div className={styles.heroGrid} />
        <div className={styles.heroGlow} />
        <div className={`${styles.container} ${styles.heroContent}`}>
          <span className={`${styles.badge} ${styles.heroFadeUp}`}>
            {t({ id: 'mall.hero.badge', defaultMessage: '改变世界价值锚定' })}
          </span>
          <div className={styles.heroTitleWrap}>
            <h1 className={styles.heroTitleTyping} aria-label={title}>
              <span aria-hidden="true">{typedTitle}</span>
            </h1>
            {blinking ? (
              <span className={styles.caret} aria-hidden="true" />
            ) : null}
          </div>
          <p
            className={`${styles.heroSubtitle} ${styles.heroFadeUp}`}
            style={{ animationDelay: '160ms' }}
          >
            {t({
              id: 'mall.hero.subtitle',
              defaultMessage:
                '每一份耕耘都要被看见与认可，每一份信任都值得被尊重。',
            })}
          </p>
          <Row
            justify="center"
            gutter={[12, 12]}
            className={styles.heroFadeUp}
            style={{ animationDelay: '260ms' }}
          >
            <Col>
              <Button type="primary" size="large" href="/products">
                {t({ id: 'mall.nav.products', defaultMessage: '商品' })}
                <ArrowRightOutlined />
              </Button>
            </Col>
            <Col>
              <Button size="large" href="/user/login">
                {t({ id: 'mall.hero.ctaAuth', defaultMessage: '登录 / 注册' })}
              </Button>
            </Col>
          </Row>

          <Row justify="center" gutter={[56, 24]} style={{ marginTop: 56 }}>
            {[
              {
                value: products.length,
                id: 'in-sale',
                label: t({
                  id: 'mall.stats.products',
                  defaultMessage: '在售商品',
                }),
              },
              {
                value: shopCount,
                id: 'shops',
                label: t({
                  id: 'mall.stats.shops',
                  defaultMessage: '卖家店铺',
                }),
              },
            ].map((item) => (
              <Col key={item.id}>
                <div className={styles.statValue}>{item.value}</div>
                <div className={styles.statLabel}>{item.label}</div>
              </Col>
            ))}
          </Row>
        </div>
      </section>
    </MallShell>
  );
}
