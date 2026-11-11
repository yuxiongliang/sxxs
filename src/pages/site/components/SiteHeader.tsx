import {
  BulbFilled,
  BulbOutlined,
  DesktopOutlined,
  GlobalOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import {
  getAllLocales,
  getLocale,
  setLocale,
  useIntl,
  useModel,
} from '@umijs/max';
import { Button, Dropdown } from 'antd';
import { useEffect, useMemo } from 'react';
import type { ThemeMode } from '@/theme';
import { useAppTheme } from '@/theme';
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

/** 顶部导航按钮：全部为页内锚点，点击平滑滚动 */
const NAV_ANCHORS = [
  { id: 'site.nav.features', href: '#features' },
  { id: 'site.nav.modules', href: '#modules' },
  { id: 'site.nav.quickstart', href: '#quickstart' },
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

export default function SiteHeader({ entries }: { entries: SearchEntry[] }) {
  const { styles } = useStyles();
  const { formatMessage } = useIntl();
  const { initialState, setInitialState } = useModel('@@initialState');
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

  const scrollTo = (href: string) => {
    document
      .querySelector(href)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <div className={styles.headerInner}>
          <a className={styles.brand} href="/">
            <ShopOutlined style={{ color: 'var(--ant-color-primary)' }} />
            {formatMessage({
              id: 'site.hero.title',
              defaultMessage: '赛霄玄思',
            })}
          </a>

          <nav className={styles.nav}>
            {NAV_ANCHORS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={styles.navButton}
                onClick={() => scrollTo(item.href)}
              >
                {formatMessage({ id: item.id, defaultMessage: item.id })}
              </button>
            ))}
            <a className={styles.navButton} href="/welcome">
              {formatMessage({ id: 'site.nav.docs', defaultMessage: '文档' })}
            </a>
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

            {signedIn ? (
              <Button type="primary" href="/dashboard/analysis">
                {formatMessage({
                  id: 'site.nav.console',
                  defaultMessage: '进入控制台',
                })}
              </Button>
            ) : (
              <>
                <Button type="text" href="/user/login">
                  {formatMessage({
                    id: 'site.nav.login',
                    defaultMessage: '登录',
                  })}
                </Button>
                <Button type="primary" href="/user/register">
                  {formatMessage({
                    id: 'site.footer.link.register',
                    defaultMessage: '注册',
                  })}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
