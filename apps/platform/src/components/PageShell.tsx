import { PageContainer } from '@ant-design/pro-components';
import type { ReactNode } from 'react';

interface PageShellProps {
  title: string;
  subTitle?: string;
  icon?: ReactNode;
  extra?: ReactNode;
  children: ReactNode;
}

/** 与控制台 SettingPage 对齐的页面外壳，平台端各页统一用它。 */
export default function PageShell({
  title,
  subTitle,
  icon,
  extra,
  children,
}: PageShellProps) {
  return (
    <PageContainer
      header={{
        title,
        subTitle,
        avatar: icon ? { icon, shape: 'square' } : undefined,
      }}
      extra={extra}
    >
      {children}
    </PageContainer>
  );
}
