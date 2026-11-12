import {
  LogoutOutlined,
  MoonOutlined,
  SunOutlined,
  TranslationOutlined,
} from '@ant-design/icons';
import { getLocale, history, setLocale, useIntl } from '@umijs/max';
import { useAppTheme } from '@shared';
import { Dropdown, Space, Typography } from 'antd';
import type { PlatformAuthUser } from '@/services/api';
import { logout } from '@/services/api';
import { tokens } from '@/services/http';

export default function PlatformAvatar({ user }: { user?: PlatformAuthUser }) {
  const { setMode } = useAppTheme();
  const intl = useIntl();

  const items = [
    {
      key: 'light',
      icon: <SunOutlined />,
      label: intl.formatMessage({ id: 'theme.light' }),
    },
    {
      key: 'dark',
      icon: <MoonOutlined />,
      label: intl.formatMessage({ id: 'theme.dark' }),
    },
    {
      key: 'lang',
      icon: <TranslationOutlined />,
      label: getLocale() === 'zh-CN' ? 'English' : '中文',
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: intl.formatMessage({ id: 'avatar.logout' }),
    },
  ];

  const onClick = async ({ key }: { key: string }) => {
    if (key === 'light' || key === 'dark') {
      setMode(key);
      return;
    }
    if (key === 'lang') {
      setLocale(getLocale() === 'zh-CN' ? 'en-US' : 'zh-CN', false);
      return;
    }
    if (key === 'logout') {
      try {
        await logout();
      } catch {
        /* 退出失败也要清掉本地会话 */
      }
      tokens.clear();
      history.push('/login');
    }
  };

  return (
    <Dropdown menu={{ items, onClick }}>
      <Space style={{ cursor: 'pointer' }}>
        <Typography.Text>
          {user?.nickname ?? user?.username ?? 'platform'}
        </Typography.Text>
      </Space>
    </Dropdown>
  );
}
