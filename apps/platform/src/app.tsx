/**
 * 赛霄玄思 SaaS 管理平台的运行时入口。
 *
 * 与租户控制台的关键差异：
 *   - token 存在 sxxs_platform_access_token，token 的 aud=platform；
 *   - 只接平台配置与租户/计费，没有任何业务菜单；
 *   - 未登录一律回 /login。
 */
import type { RunTimeLayoutConfig } from '@umijs/max';
import { getIntl, history } from '@umijs/max';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App as AntdApp } from 'antd';
import type { MenuDataItem } from '@ant-design/pro-components';
import type { ReactNode } from 'react';
import { AppThemeProvider } from '@shared';
import PlatformAvatar from '@/components/PlatformAvatar';
import type { PlatformAuthUser } from '@/services/api';
import { platformMe } from '@/services/api';
import { tokens } from '@/services/http';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
});

export interface PlatformInitialState {
  user?: PlatformAuthUser;
  permissions?: string[];
}

export async function getInitialState(): Promise<PlatformInitialState> {
  if (!tokens.get()) return {};
  try {
    const me = await platformMe();
    return { user: me.user, permissions: me.permissions };
  } catch {
    tokens.clear();
    return {};
  }
}

/**
 * 把路由 name 翻译成菜单文案。
 *
 * Umi 的 layout 插件默认直接渲染 name 字面量（显示成 tenants / settings），
 * 所以这里显式查一次词表；name 同时也作为 locale key 使用。
 */
function translateMenu(items: MenuDataItem[]): MenuDataItem[] {
  return items.map((item) => ({
    ...item,
    name: item.name
      ? getIntl().formatMessage({ id: item.name, defaultMessage: item.name })
      : item.name,
    children: item.children ? translateMenu(item.children) : item.children,
  }));
}

export const layout: RunTimeLayoutConfig = ({ initialState }) => ({
  title: '赛霄玄思 SaaS 管理平台',
  layout: 'side',
  menuDataRender: translateMenu,
  avatarProps: {
    render: () => <PlatformAvatar user={initialState?.user} />,
  },
  onPageChange: () => {
    if (!tokens.get() && history.location.pathname !== '/login') {
      history.push('/login');
    }
  },
});

export function rootContainer(container: ReactNode) {
  return (
    <AppThemeProvider>
      <AntdApp>
        <QueryClientProvider client={queryClient}>{container}</QueryClientProvider>
      </AntdApp>
    </AppThemeProvider>
  );
}
