import { PageContainer } from '@ant-design/pro-components';
import type { ReactNode } from 'react';

interface SettingPageProps {
  title: string;
  subTitle?: string;
  icon?: ReactNode;
  extra?: ReactNode;
  children: ReactNode;
}

export default function SettingPage({
  title,
  subTitle,
  icon,
  extra,
  children,
}: SettingPageProps) {
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
