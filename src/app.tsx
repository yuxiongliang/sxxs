import { LinkOutlined } from '@ant-design/icons';
import type { Settings as LayoutSettings } from '@ant-design/pro-components';
import { SettingDrawer } from '@ant-design/pro-components';
import type { RequestConfig, RunTimeLayoutConfig } from '@umijs/max';
import { history, Link } from '@umijs/max';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import React from 'react';

// Initialize dayjs plugins globally
dayjs.extend(relativeTime);

import {
  AvatarDropdown,
  DocLink,
  ErrorBoundary,
  Footer,
  LangDropdown,
  OfflineBanner,
  PageTabs,
  VersionDropdown,
} from '@/components';
import { type AuthTenant, me as queryMe } from '@/services/auth/api';
import { getTenantSubscription } from '@/services/tenantBilling';
import { AppThemeProvider } from '@/theme';
import { clearAccessToken, getAccessToken } from '@/utils/authToken';
import { refreshAccessToken } from '@/utils/refreshToken';
import defaultSettings from '../config/defaultSettings';
import { errorConfig } from './requestErrorConfig';

const isDev = process.env.NODE_ENV === 'development';
const loginPath = '/user/login';

/**
 * 无需登录即可访问的路径。
 * 根路径是公开落地页 —— 未登录用户不应被弹到登录页。
 */
const PUBLIC_PATHS = [
  '/',
  '/site',
  // 商城前台：商品列表与商品详情都允许匿名浏览
  '/products',
  // 商品详情的旧路径（现为重定向到 /products/:id），保留公开以免旧链接先被登录拦截
  '/portal/products',
  loginPath,
  '/user/register',
  '/user/register-result',
];

/**
 * 公开路径判断。
 *
 * 必须支持**前缀匹配**：`/products/1` 这类带参数的详情页也要算公开，
 * 否则商品详情会被当成受保护页面弹去登录。
 * 根路径 '/' 只做精确匹配，否则会把全站都判成公开。
 */
const isPublicPath = (pathname: string) =>
  PUBLIC_PATHS.some(
    (base) =>
      pathname === base || (base !== '/' && pathname.startsWith(`${base}/`)),
  );

/**
 * @see https://umijs.org/docs/api/runtime-config#getinitialstate
 * */
export async function getInitialState(): Promise<{
  settings?: Partial<LayoutSettings>;
  currentUser?: API.CurrentUser;
  loading?: boolean;
  fetchUserInfo?: () => Promise<API.CurrentUser | undefined>;
  settingDrawerOpen?: boolean;
  permissions?: string[];
  roles?: string[];
  tenants?: AuthTenant[];
  currentTenant?: AuthTenant;
  /** Feature keys of the tenant's plan; undefined when the plan is unknown. */
  features?: string[];
}> {
  const redirectToLogin = () => {
    const { pathname, search, hash } = history.location;
    history.replace(
      `${loginPath}?redirect=${encodeURIComponent(pathname + search + hash)}`,
    );
  };

  const toCurrentUser = (session: Awaited<ReturnType<typeof queryMe>>) =>
    ({
      name: session.user.nickname,
      avatar: session.user.avatar ?? undefined,
      userid: String(session.user.id),
      email: session.user.email,
      access:
        session.roles.includes('admin') ||
        session.roles.includes('platform_admin') ||
        session.roles.includes('tenant_owner')
          ? 'admin'
          : 'user',
    }) as API.CurrentUser;

  const fetchSession = async () => {
    // access token 存在 sessionStorage，**按标签页隔离** —— 新标签页打开控制台、
    // 或直接输入受保护链接时，本页是没有 token 的。但 HttpOnly cookie 里的
    // refresh token 是跨标签页共享的，所以先静默续期，避免让已登录用户再登一次。
    let token = getAccessToken();
    if (!token) {
      token = await refreshAccessToken();
      if (!token) {
        redirectToLogin();
        return undefined;
      }
    }
    try {
      return await queryMe();
    } catch (_error) {
      clearAccessToken();
      redirectToLogin();
      return undefined;
    }
  };

  /**
   * 公开页面（如站点根 /）的「静默恢复登录态」。
   *
   * 关键点：token 存在 sessionStorage 里，**按标签页隔离** —— 用户在新标签页登录后，
   * 首页那个标签页读不到 token。但 refresh token 在 HttpOnly cookie 里，是跨标签页共享的，
   * 所以这里用 cookie 换一次 access token，就能识别出「其实已经登录」。
   *
   * 换不到就当作匿名访客，绝不跳登录（公开页允许未登录浏览）。
   */
  const tryRestoreSession = async () => {
    try {
      let token = getAccessToken();
      if (!token) token = await refreshAccessToken();
      if (!token) return undefined;
      return await queryMe();
    } catch (_error) {
      clearAccessToken();
      return undefined;
    }
  };

  const fetchUserInfo = async () => {
    const session = await fetchSession();
    return session ? toCurrentUser(session) : undefined;
  };

  /**
   * Plan feature keys drive the menu/route gates in `src/access.ts`.
   *
   * A failure returns `undefined` on purpose: the gates then fail open, so a
   * billing outage degrades to "everything visible" instead of locking every
   * operator out of the console. The backend still enforces quotas/permissions.
   */
  const fetchPlanFeatures = async (): Promise<string[] | undefined> => {
    try {
      const report = await getTenantSubscription();
      return report.plan?.features ?? [];
    } catch (_error) {
      return undefined;
    }
  };

  // 如果不是登录页面，执行
  const { location } = history;
  if (!isPublicPath(location.pathname)) {
    const session = await fetchSession();
    const features = session ? await fetchPlanFeatures() : undefined;
    return {
      fetchUserInfo,
      currentUser: session ? toCurrentUser(session) : undefined,
      permissions: session?.permissions ?? [],
      roles: session?.roles ?? [],
      tenants: session?.tenants ?? [],
      currentTenant: session?.current_tenant,
      features,
      settings: defaultSettings as Partial<LayoutSettings>,
      settingDrawerOpen: false,
    };
  }
  // 公开页面也要识别登录态：已登录时导航显示「进入控制台」
  const publicSession = await tryRestoreSession();
  const publicFeatures = publicSession ? await fetchPlanFeatures() : undefined;
  return {
    fetchUserInfo,
    currentUser: publicSession ? toCurrentUser(publicSession) : undefined,
    permissions: publicSession?.permissions ?? [],
    roles: publicSession?.roles ?? [],
    tenants: publicSession?.tenants ?? [],
    currentTenant: publicSession?.current_tenant,
    features: publicFeatures,
    settings: defaultSettings as Partial<LayoutSettings>,
    settingDrawerOpen: false,
  };
}

/**
 * 模板自带的演示分组，只作为脚手架参考，不属于本产品的业务菜单。
 *
 * 只隐藏**侧边栏入口**，路由本身保留：直接输入 URL 仍然可达，历史链接与
 * 文档里的示例链接不会 404。要彻底下线某个分组，再删对应路由。
 */
const HIDDEN_MENU_PATHS = [
  '/form',
  '/list',
  '/profile',
  '/result',
  '/exception',
  '/account',
  // 同样是模板演示：多级菜单示例页 / AI 聊天示例
  '/admin',
  '/chatbot',
];

type MenuNode = { path?: string; children?: MenuNode[] };

function hideDemoMenus(nodes: MenuNode[]): MenuNode[] {
  return nodes
    .filter((node) => {
      const path = node.path ?? '';
      return !HIDDEN_MENU_PATHS.some(
        (hidden) => path === hidden || path.startsWith(`${hidden}/`),
      );
    })
    .map((node) =>
      node.children
        ? { ...node, children: hideDemoMenus(node.children) }
        : node,
    );
}

// ProLayout 支持的api https://procomponents.ant.design/components/layout
export const layout: RunTimeLayoutConfig = ({
  initialState,
  setInitialState,
}) => {
  return {
    menuItemRender: (item, dom) => {
      if (item.path) {
        return (
          <Link to={item.path} prefetch>
            {dom}
          </Link>
        );
      }
      return dom;
    },
    actionsRender: () => {
      // `locale: false` opts out of the language switcher. ProLayout's own
      // `locale` prop is a locale string, so narrow to the boolean toggle here.
      const localeEnabled =
        (initialState?.settings as { locale?: boolean })?.locale !== false;
      return [
        <DocLink key="doc" />,
        <VersionDropdown key="version" />,
        localeEnabled && <LangDropdown key="lang" />,
      ].filter(Boolean);
    },
    avatarProps: {
      src: initialState?.currentUser?.avatar,
      title: 'ProUser',
      render: (_, avatarChildren) => (
        <AvatarDropdown>{avatarChildren}</AvatarDropdown>
      ),
    },
    // waterMarkProps: {
    //   content: initialState?.currentUser?.name,
    // },
    footerRender: () => <Footer />,
    onPageChange: () => {
      const { location } = history;
      // 如果没有登录，重定向到 login
      if (!initialState?.currentUser && !isPublicPath(location.pathname)) {
        history.replace(
          `${loginPath}?redirect=${encodeURIComponent(location.pathname + location.search + location.hash)}`,
        );
      }
    },
    bgLayoutImgList: [
      {
        src: 'https://mdn.alipayobjects.com/yuyan_qk0oxh/afts/img/D2LWSqNny4sAAAAAAAAAAAAAFl94AQBr',
        left: 85,
        bottom: 100,
        height: '303px',
      },
      {
        src: 'https://mdn.alipayobjects.com/yuyan_qk0oxh/afts/img/C2TWRpJpiC0AAAAAAAAAAAAAFl94AQBr',
        bottom: -68,
        right: -45,
        height: '303px',
      },
      {
        src: 'https://mdn.alipayobjects.com/yuyan_qk0oxh/afts/img/F6vSTbj8KpYAAAAAAAAAAAAAFl94AQBr',
        bottom: 0,
        left: 0,
        width: '331px',
      },
    ],
    links: isDev
      ? [
          <Link key="openapi" to="/umi/plugin/openapi" target="_blank">
            <LinkOutlined />
            <span>OpenAPI 文档</span>
          </Link>,
        ]
      : [],
    // Replace ProLayout's default ErrorBoundary with our offline-aware version,
    // so chunk load errors show friendly messages instead of "Something went wrong."
    ErrorBoundary,
    // 侧边栏只保留本产品自己的菜单（见 HIDDEN_MENU_PATHS）。
    menuDataRender: (menuData) => hideDemoMenus(menuData as MenuNode[]) as any,
    menuHeaderRender: undefined,
    // 自定义 403 页面
    // unAccessible: <div>unAccessible</div>,
    // 增加一个 loading 的状态
    childrenRender: (children) => {
      // if (initialState?.loading) return <PageLoading />;
      return (
        <>
          <PageTabs />
          {children}
          <SettingDrawer
            disableUrlParams
            enableDarkTheme
            collapse={initialState?.settingDrawerOpen}
            onCollapseChange={(open) => {
              setInitialState((s) => ({
                ...s,
                settingDrawerOpen: open,
              }));
            }}
            settings={initialState?.settings}
            onSettingChange={(settings) => {
              setInitialState((s) => ({
                ...s,
                settings,
              }));
            }}
          />
        </>
      );
    },
    ...initialState?.settings,
  };
};

// Never hardcode a host here. The default is same-origin (''):
//   * dev  -> config/proxy.ts forwards /api/v1 to the local FastAPI at :9000
//   * prod -> serve the SPA and /api/v1 behind one origin (nginx / reverse proxy)
// Set API_BASE_URL only when the API really lives on another host
// (config/config.ts already defines it, defaulting to '').
/**
 * @name request 配置，可以配置错误处理
 * 它基于 axios 提供了一套统一的网络请求和错误处理方案。
 * @doc https://umijs.org/docs/max/request#配置
 */
export const request: RequestConfig = {
  baseURL: process.env.API_BASE_URL || '',
  ...errorConfig,
};

export function rootContainer(container: React.ReactNode) {
  // AppThemeProvider 必须在最外层：antd 的弹窗/下拉/消息走 portal 到 body，
  // 只有包到根上，它们才拿得到暗色主题。
  return (
    <AppThemeProvider>
      <OfflineBanner />
      <ErrorBoundary>{container}</ErrorBoundary>
    </AppThemeProvider>
  );
}
