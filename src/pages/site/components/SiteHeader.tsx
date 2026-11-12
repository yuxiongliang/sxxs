import {
  BulbFilled,
  BulbOutlined,
  DesktopOutlined,
  DownOutlined,
  GlobalOutlined,
  LogoutOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import {
  getAllLocales,
  getLocale,
  setLocale,
  useAccess,
  useIntl,
  useModel,
} from '@umijs/max';
import { Button, Dropdown } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { logout as authLogout } from '@/services/auth/api';
import type { ThemeMode } from '@/theme';
import { useAppTheme } from '@/theme';
import { clearAccessToken } from '@/utils/authToken';
import { visibleEntrances } from '../entrances';
import type { SearchEntry } from '../search';
import useStyles from '../style';
import GlobalSearch from './GlobalSearch';

const LOCALE_LABEL: Record<string, string> = {
  'zh-CN': '简体中文',
  'zh-TW': '繁體中文',
  'en-US': 'English',
  'ja-JP': '日本語',
  'pt-BR': 'Português',
  'id-ID': 'Bahasa Indonesia',
  'fa-IR': 'فارسی',
  'bn-BD': 'বাংলা',
};

/** 顶部导航项：页内跳转用 onClick，站内跳转用 href */
export interface SiteNavItem {
  key: string;
  labelId: string;
  defaultLabel: string;
  href?: string;
  onClick?: () => void;
}

/** 旧落地页（营销页）的默认导航 */
const MARKETING_NAV: SiteNavItem[] = [
  {
    key: 'features',
    labelId: 'site.nav.features',
    defaultLabel: '平台能力',
    href: '#features',
  },
  {
    key: 'modules',
    labelId: 'site.nav.modules',
    defaultLabel: '功能模块',
    href: '#modules',
  },
  {
    key: 'quickstart',
    labelId: 'site.nav.quickstart',
    defaultLabel: '快速开始',
    href: '#quickstart',
  },
];

const THEME_OPTIONS: Array<{
  key: ThemeMode;
  labelId: string;
  defaultLabel: string;
  icon: React.ReactNode;
}> = [
  {
    key: 'light',
    labelId: 'site.theme.light',
    defaultLabel: '亮色',
    icon: <BulbOutlined />,
  },
  {
    key: 'dark',
    labelId: 'site.theme.dark',
    defaultLabel: '暗色',
    icon: <BulbFilled />,
  },
  {
    key: 'system',
    labelId: 'site.theme.system',
    defaultLabel: '跟随系统',
    icon: <DesktopOutlined />,
  },
];

export default function SiteHeader({
  entries,
  nav,
  activeKey,
  showAuth = true,
}: {
  entries: SearchEntry[];
  /** 不传则使用营销页默认导航 */
  nav?: SiteNavItem[];
  /** 当前高亮的导航项 key */
  activeKey?: string;
  /** 是否渲染登录/注册/控制台/账号入口。纯介绍页传 false */
  showAuth?: boolean;
}) {
  const { styles } = useStyles();
  const { formatMessage } = useIntl();
  const { initialState, setInitialState, refresh } = useModel('@@initialState');
  const { mode, resolved, setMode } = useAppTheme();
  const signedIn = Boolean(initialState?.currentUser);

  // 控制台的 ProLayout 也跟随全局主题，避免暗色下侧边栏仍是亮色。
  // 注意 ProLayout 的取值是 'light' | 'realDark'，不是 'dark'，必须映射。
  useEffect(() => {
    const navTheme = resolved === 'dark' ? 'realDark' : 'light';
    if (!initialState || initialState.settings?.navTheme === navTheme) return;
    setInitialState({
      ...initialState,
      settings: { ...initialState.settings, navTheme },
    });
  }, [resolved, initialState, setInitialState]);

  // 从别的标签页登录回来后，重新识别一次登录态。
  // token 在 sessionStorage 里按标签页隔离，但 refresh cookie 是共享的，
  // 所以这里 re-run getInitialState 会用 cookie 静默换到 token。
  useEffect(() => {
    const recheck = () => {
      if (document.visibilityState !== 'visible') return;
      if (initialState?.currentUser) return;
      refresh();
    };
    document.addEventListener('visibilitychange', recheck);
    window.addEventListener('focus', recheck);
    return () => {
      document.removeEventListener('visibilitychange', recheck);
      window.removeEventListener('focus', recheck);
    };
  }, [initialState?.currentUser, refresh]);

  const handleLogout = async () => {
    // 后端失败也要把本地登出做完，否则用户会卡在「看似已登录」的状态里
    try {
      await authLogout();
    } catch {
      /* 忽略：下面照常清理本地状态 */
    }
    clearAccessToken();
    await refresh();
  };

  const locales = useMemo(() => {
    const current = getLocale();
    return getAllLocales()
      .filter((locale) => locale in LOCALE_LABEL)
      .map((locale) => ({
        key: locale,
        label:
          (locale === current ? '✓ ' : '\u00a0\u00a0') + LOCALE_LABEL[locale],
      }));
  }, []);

  const themeItems = THEME_OPTIONS.map((option) => ({
    key: option.key,
    icon: option.icon,
    label:
      (mode === option.key ? '✓ ' : '\u00a0\u00a0') +
      formatMessage({
        id: option.labelId,
        defaultMessage: option.defaultLabel,
      }),
  }));

  const activeTheme =
    THEME_OPTIONS.find((option) => option.key === mode) ?? THEME_OPTIONS[2];

  // 悬停「进入控制台」时列出的一级页面：只收当前账号真正有权访问的，
  // 权限判定复用 src/access.ts，避免菜单里出现「点进去 403」的条目。
  const access = useAccess();
  const consoleMenuItems = visibleEntrances(access).map((entry) => ({
    key: entry.key,
    label: formatMessage({ id: entry.labelId, defaultMessage: entry.key }),
    // 同标签页跳转：access token 在本页 sessionStorage 里，
    // 不会出现「新标签页没 token → 又要登录」的问题。
    onClick: () => window.location.assign(entry.path),
  }));
  const navItems = nav ?? MARKETING_NAV;

  const handleNav = (item: SiteNavItem) => {
    if (item.onClick) {
      item.onClick();
      return;
    }
    if (!item.href) return;
    if (item.href.startsWith('#')) {
      // 页内锚点：平滑滚动，不刷新页面
      document
        .querySelector(item.href)
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    // 站内跳转（如「赛霄玄思」去旧落地页）
    window.location.assign(item.href);
  };

  // 站点品牌：匿名公开接口。
  // 租户由后端按请求 Host 解析（B6），前端不再传 tenant 参数 ——
  // 本地开发时 Host 解析不出租户，后端会兜底到 demo（TENANT_HOST_FALLBACK）。
  const [brand, setBrand] = useState<{
    display_name: string;
    logo_url?: string | null;
  }>();

  useEffect(() => {
    let cancelled = false;
    fetch('/api/v1/public/brand')
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (!cancelled && body?.data) setBrand(body.data);
      })
      .catch(() => {
        /* 品牌取不到就用默认文案，不能影响站点可用性 */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (brand?.display_name) {
      document.title = brand.display_name;
    }
  }, [brand?.display_name]);

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <div className={styles.headerInner}>
          <a className={styles.brand} href="/">
            {brand?.logo_url ? (
              <img
                src={brand.logo_url}
                alt={brand.display_name}
                style={{ height: 26, objectFit: 'contain' }}
              />
            ) : (
              <ShopOutlined style={{ color: 'var(--ant-color-primary)' }} />
            )}
            {brand?.display_name ??
              formatMessage({
                id: 'site.hero.title',
                defaultMessage: '赛霄玄思',
              })}
          </a>

          <nav className={styles.nav}>
            {navItems.map((item) => (
              <button
                key={item.key}
                type="button"
                className={styles.navButton}
                aria-current={activeKey === item.key ? 'page' : undefined}
                data-active={activeKey === item.key ? 'true' : undefined}
                onClick={() => handleNav(item)}
              >
                {formatMessage({
                  id: item.labelId,
                  defaultMessage: item.defaultLabel,
                })}
              </button>
            ))}
          </nav>

          <div className={styles.actions}>
            <GlobalSearch entries={entries} />

            <Dropdown
              menu={{
                items: themeItems,
                selectable: true,
                selectedKeys: [mode],
                onClick: ({ key }) => setMode(key as ThemeMode),
              }}
              placement="bottomRight"
            >
              <Button
                type="text"
                // 无障碍名称描述「当前是哪种模式」，而不是只有图标
                aria-label={formatMessage({
                  id: activeTheme.labelId,
                  defaultMessage: activeTheme.defaultLabel,
                })}
                icon={activeTheme.icon}
              />
            </Dropdown>

            <Dropdown
              menu={{
                items: locales,
                onClick: ({ key }) => setLocale(key, true),
              }}
              placement="bottomRight"
            >
              <Button
                type="text"
                aria-label={formatMessage({
                  id: 'site.lang.label',
                  defaultMessage: '语言',
                })}
                icon={<GlobalOutlined />}
              />
            </Dropdown>

            {showAuth ? (
              signedIn ? (
                <>
                  {/* 已登录：悬停「进入控制台」直接列出有权访问的一级页面 */}
                  <Dropdown
                    menu={{ items: consoleMenuItems }}
                    trigger={['hover']}
                    placement="bottomRight"
                    disabled={consoleMenuItems.length === 0}
                  >
                    <Button type="primary" href="/dashboard/analysis">
                      {formatMessage({
                        id: 'site.nav.console',
                        defaultMessage: '进入控制台',
                      })}
                      <DownOutlined style={{ fontSize: 10 }} />
                    </Button>
                  </Dropdown>

                  <Dropdown
                    menu={{
                      items: [
                        {
                          key: 'logout',
                          icon: <LogoutOutlined />,
                          label: formatMessage({
                            id: 'site.nav.logout',
                            defaultMessage: '退出登录',
                          }),
                        },
                      ],
                      onClick: ({ key }) => {
                        if (key === 'logout') handleLogout();
                      },
                    }}
                    placement="bottomRight"
                  >
                    <button type="button" className={styles.accountBtn}>
                      <span className={styles.accountAvatar}>
                        {(initialState?.currentUser?.name ?? '?').slice(0, 1)}
                      </span>
                      <span className={styles.accountName}>
                        {initialState?.currentUser?.name}
                      </span>
                      <DownOutlined className={styles.accountArrow} />
                    </button>
                  </Dropdown>
                </>
              ) : (
                <>
                  <Button
                    type="text"
                    href="/user/login"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {formatMessage({
                      id: 'site.nav.login',
                      defaultMessage: '登录',
                    })}
                  </Button>
                  <Button
                    type="primary"
                    href="/user/register"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {formatMessage({
                      id: 'site.footer.link.register',
                      defaultMessage: '注册',
                    })}
                  </Button>
                </>
              )
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
