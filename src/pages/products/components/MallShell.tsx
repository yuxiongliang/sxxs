import { useIntl } from '@umijs/max';
import type { ReactNode } from 'react';
import type { SearchEntry } from '@/pages/site/search';
import type { SiteNavItem } from '@/pages/site/components/SiteHeader';
import SiteHeader from '@/pages/site/components/SiteHeader';
import SiteFooter from '@/pages/site/components/SiteFooter';
import useStyles from '@/pages/site/style';

/**
 * 商城前台外壳：`/`、`/products`、`/products/:id` 共用。
 *
 * 导航固定三项（首页 / 商品 / 赛霄玄思），与站点根保持一致；
 * 用户登录态、主题、语言、搜索都由 SiteHeader 统一提供。
 */
export default function MallShell({
  activeKey,
  children,
}: {
  activeKey: 'home' | 'products';
  children: ReactNode;
}) {
  const { styles } = useStyles();
  const { formatMessage: t } = useIntl();

  const nav: SiteNavItem[] = [
    {
      key: 'home',
      labelId: 'mall.nav.home',
      defaultLabel: '首页',
      href: '/',
    },
    {
      key: 'products',
      labelId: 'mall.nav.products',
      defaultLabel: '商品',
      href: '/products',
    },
    {
      key: 'brand',
      labelId: 'mall.nav.brand',
      defaultLabel: '赛霄玄思',
      href: '/site',
    },
  ];

  const entries: SearchEntry[] = nav.map((item) => ({
    id: `nav-${item.key}`,
    group: 'nav',
    title: t({ id: item.labelId, defaultMessage: item.defaultLabel }),
    href: item.href ?? '/',
  }));

  return (
    <div className={styles.shell}>
      <SiteHeader entries={entries} nav={nav} activeKey={activeKey} />
      <main>{children}</main>
      <SiteFooter />
    </div>
  );
}
