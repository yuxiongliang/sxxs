import { CloseCircleOutlined } from '@ant-design/icons';
import { history, useIntl, useLocation, useSelectedRoutes } from '@umijs/max';
import { Button, Tabs, theme } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';

interface PageTab {
  path: string;
  nameKey: string;
  closable: boolean;
}

const HOME_TAB: PageTab = {
  path: '/dashboard/analysis',
  nameKey: 'menu.dashboard.analysis',
  closable: false,
};

function normalizePath(pathname: string) {
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.replace(/\/+$/, '');
  }
  return pathname || '/';
}

const PageTabs: React.FC = () => {
  const location = useLocation();
  const selectedRoutes = useSelectedRoutes();
  const intl = useIntl();
  const { token } = theme.useToken();
  const path = normalizePath(location.pathname);

  const routeNames = useMemo(
    () =>
      selectedRoutes
        .map((item: any) => item?.route?.name)
        .filter(
          (name: unknown): name is string =>
            typeof name === 'string' && name.length > 0,
        ),
    [selectedRoutes],
  );

  const currentNameKey = routeNames.length
    ? `menu.${routeNames.join('.')}`
    : path;
  const [tabs, setTabs] = useState<PageTab[]>([HOME_TAB]);

  useEffect(() => {
    if (path === '/' || path.startsWith('/user/')) return;
    setTabs((previous) => {
      if (previous.some((tab) => tab.path === path)) return previous;
      return [...previous, { path, nameKey: currentNameKey, closable: true }];
    });
  }, [currentNameKey, path]);

  const closeTab = (targetPath: string) => {
    if (targetPath === HOME_TAB.path) return;
    const index = tabs.findIndex((tab) => tab.path === targetPath);
    const nextTabs = tabs.filter((tab) => tab.path !== targetPath);
    setTabs(nextTabs);
    if (path === targetPath) {
      const fallback = nextTabs[Math.max(0, index - 1)] ?? HOME_TAB;
      history.push(fallback.path);
    }
  };

  const closeAll = () => {
    setTabs([HOME_TAB]);
    if (path !== HOME_TAB.path) history.push(HOME_TAB.path);
  };

  const items = tabs.map((tab) => ({
    key: tab.path,
    label: intl.formatMessage({
      id: tab.nameKey,
      defaultMessage: tab.path,
    }),
    closable: tab.closable,
  }));

  return (
    <div
      className="page-tabs-bar"
      style={{
        background: token.colorBgContainer,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        padding: '8px 16px 0',
      }}
    >
      <Tabs
        size="small"
        type="editable-card"
        hideAdd
        activeKey={path}
        items={items}
        onChange={(key) => history.push(key)}
        onEdit={(targetKey, action) => {
          if (action === 'remove' && typeof targetKey === 'string') {
            closeTab(targetKey);
          }
        }}
        tabBarExtraContent={
          <Button
            type="text"
            size="small"
            icon={<CloseCircleOutlined />}
            disabled={tabs.length <= 1}
            onClick={closeAll}
          >
            关闭全部
          </Button>
        }
        style={{ marginBottom: 0 }}
      />
    </div>
  );
};

export default PageTabs;
