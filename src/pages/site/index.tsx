import {
  AuditOutlined,
  BarChartOutlined,
  ClusterOutlined,
  CreditCardOutlined,
  EnvironmentOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ShopOutlined,
  ShoppingOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Card, Col, Row } from 'antd';
import { useMemo } from 'react';
import HeroBackdrop from './components/HeroBackdrop';
import SiteFooter from './components/SiteFooter';
import SiteHeader from './components/SiteHeader';
import type { SearchEntry } from './search';
import useStyles from './style';
import { usePrefersReducedMotion } from './useReducedMotion';
import { useTypewriter } from './useTypewriter';

/** 平台端是独立系统（赛霄玄思 SaaS 管理平台），这里只做跨系统跳转。 */
const PLATFORM_CONSOLE_URL = 'http://localhost:8001/tenants';

const FEATURES = [
  { key: 'saas', icon: <SafetyCertificateOutlined />, href: '/users/list' },
  { key: 'seller', icon: <ShopOutlined />, href: '/portal/seller' },
  { key: 'trade', icon: <ShoppingOutlined />, href: '/orders' },
  { key: 'finance', icon: <WalletOutlined />, href: '/finance' },
  { key: 'im', icon: <MessageOutlined />, href: '/messages' },
  { key: 'billing', icon: <AuditOutlined />, href: '/system/audit' },
];

const MODULES = [
  { key: 'auth', icon: <SafetyCertificateOutlined />, href: '/users/roles' },
  { key: 'tenant', icon: <ClusterOutlined />, href: PLATFORM_CONSOLE_URL },
  { key: 'seller', icon: <ShopOutlined />, href: '/sellers' },
  { key: 'product', icon: <ShoppingOutlined />, href: '/products' },
  { key: 'order', icon: <ShoppingOutlined />, href: '/orders' },
  { key: 'im', icon: <MessageOutlined />, href: '/messages' },
  { key: 'finance', icon: <WalletOutlined />, href: '/finance' },
  { key: 'billing', icon: <CreditCardOutlined />, href: PLATFORM_CONSOLE_URL },
  { key: 'audit', icon: <AuditOutlined />, href: '/system/audit' },
  { key: 'dashboard', icon: <BarChartOutlined />, href: '/dashboard/analysis' },
  { key: 'map', icon: <EnvironmentOutlined />, href: '/system/settings/amap' },
  {
    key: 'settings',
    icon: <SettingOutlined />,
    href: '/system/settings/payment',
  },
];

type Translate = ReturnType<typeof useIntl>['formatMessage'];

function buildSearchEntries(t: Translate): SearchEntry[] {
  const nav: SearchEntry[] = [
    {
      id: 'nav-features',
      group: 'nav',
      title: t({ id: 'site.nav.features', defaultMessage: '平台能力' }),
      href: '#features',
    },
    {
      id: 'nav-modules',
      group: 'nav',
      title: t({ id: 'site.nav.modules', defaultMessage: '功能模块' }),
      href: '#modules',
    },
    {
      id: 'nav-quickstart',
      group: 'nav',
      title: t({ id: 'site.nav.quickstart', defaultMessage: '快速开始' }),
      href: '#quickstart',
    },
  ];

  const features: SearchEntry[] = FEATURES.map((item) => ({
    id: `feature-${item.key}`,
    group: 'feature',
    title: t({
      id: `site.feature.${item.key}.title`,
      defaultMessage: item.key,
    }),
    desc: t({ id: `site.feature.${item.key}.desc`, defaultMessage: '' }),
    href: '#features',
  }));

  const modules: SearchEntry[] = MODULES.map((item) => ({
    id: `module-${item.key}`,
    group: 'module',
    title: t({ id: `site.module.${item.key}`, defaultMessage: item.key }),
    href: '#modules',
  }));

  // 纯介绍页不提供站外/受保护页面入口，搜索只做页内跳转

  return [...nav, ...features, ...modules];
}

export default function SiteLandingPage() {
  const { styles } = useStyles();
  const { formatMessage: t } = useIntl();
  const entries = useMemo(() => buildSearchEntries(t), [t]);
  const title = t({ id: 'site.hero.title', defaultMessage: '赛霄玄思' });
  // 尊重系统的「减少动态效果」：开启时直接显示完整标题，不做打字与光标闪烁
  const reducedMotion = usePrefersReducedMotion();
  const { visible: typedTitle, blinking } = useTypewriter(title, reducedMotion);

  return (
    <div className={styles.shell}>
      <SiteHeader entries={entries} showAuth={false} />

      <main>
        <section className={styles.hero}>
          <HeroBackdrop className={styles.heroBackdrop} />
          <div className={styles.heroGrid} />
          <div className={styles.heroGlow} />
          <div className={`${styles.container} ${styles.heroContent}`}>
            <span className={`${styles.badge} ${styles.heroFadeUp}`}>
              {t({
                id: 'site.hero.badge',
                defaultMessage: '多租户 · C2C 多卖家 · SaaS 计费',
              })}
            </span>
            {/* 读屏器读完整标题；视觉上逐字出现，避免被反复朗读 */}
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
              {t({ id: 'site.hero.subtitle', defaultMessage: '' })}
            </p>

            <Row justify="center" gutter={[56, 24]} style={{ marginTop: 56 }}>
              {[
                { value: '38', id: 'site.stats.tables' },
                { value: '261', id: 'site.stats.tests' },
                { value: '12', id: 'site.stats.modules' },
              ].map((item) => (
                <Col key={item.id}>
                  <div className={styles.statValue}>{item.value}</div>
                  <div className={styles.statLabel}>
                    {t({ id: item.id, defaultMessage: item.id })}
                  </div>
                </Col>
              ))}
            </Row>
          </div>
        </section>

        <section id="features" className={styles.section}>
          <div className={styles.container}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>
                {t({ id: 'site.features.title', defaultMessage: '平台能力' })}
              </h2>
              <p className={styles.sectionSubtitle}>
                {t({ id: 'site.features.subtitle', defaultMessage: '' })}
              </p>
            </div>
            <Row gutter={[16, 16]}>
              {FEATURES.map((item) => (
                <Col xs={24} md={12} xl={8} key={item.key}>
                  <Card hoverable styles={{ body: { padding: 20 } }}>
                    <div className={styles.cardTitle}>
                      <span style={{ color: 'var(--ant-color-primary)' }}>
                        {item.icon}
                      </span>
                      {t({
                        id: `site.feature.${item.key}.title`,
                        defaultMessage: item.key,
                      })}
                    </div>
                    <p className={styles.cardDesc}>
                      {t({
                        id: `site.feature.${item.key}.desc`,
                        defaultMessage: '',
                      })}
                    </p>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>
        </section>

        <section id="modules" className={styles.section}>
          <div className={styles.container}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>
                {t({ id: 'site.modules.title', defaultMessage: '功能模块' })}
              </h2>
              <p className={styles.sectionSubtitle}>
                {t({ id: 'site.modules.subtitle', defaultMessage: '' })}
              </p>
            </div>
            <Row gutter={[12, 12]}>
              {MODULES.map((item) => (
                <Col xs={12} md={8} xl={6} key={item.key}>
                  {/* 纯介绍页：模块只做展示，不提供跳转（避免把访客引到受保护页面） */}
                  <div className={styles.moduleItem}>
                    {item.icon}
                    {t({
                      id: `site.module.${item.key}`,
                      defaultMessage: item.key,
                    })}
                  </div>
                </Col>
              ))}
            </Row>
          </div>
        </section>

        <section id="quickstart" className={styles.section}>
          <div className={styles.container}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>
                {t({
                  id: 'site.quickstart.title',
                  defaultMessage: '快速开始',
                })}
              </h2>
              <p className={styles.sectionSubtitle}>
                {t({ id: 'site.quickstart.subtitle', defaultMessage: '' })}
              </p>
            </div>
            <Row gutter={[16, 16]}>
              {['s1', 's2', 's3'].map((step, index) => (
                <Col xs={24} md={8} key={step}>
                  <Card styles={{ body: { padding: 20 } }}>
                    <div className={styles.cardTitle}>
                      <span style={{ color: 'var(--ant-color-primary)' }}>
                        {index + 1}
                      </span>
                      {t({
                        id: `site.quickstart.${step}.title`,
                        defaultMessage: step,
                      })}
                    </div>
                    <p className={styles.cardDesc}>
                      {t({
                        id: `site.quickstart.${step}.desc`,
                        defaultMessage: '',
                      })}
                    </p>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>
        </section>
      </main>

      <SiteFooter showLinks={false} />
    </div>
  );
}
