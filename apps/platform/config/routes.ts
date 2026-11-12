export default [
  {
    path: '/login',
    layout: false,
    component: './login',
  },
  { path: '/', redirect: '/tenants' },
  {
    path: '/tenants',
    name: 'tenants',
    icon: 'ClusterOutlined',
    component: './tenants',
  },
  {
    // 计费：套餐 / 账单 从原「租户与计费」页签拆成独立子菜单
    path: '/billing',
    name: 'billing',
    icon: 'WalletOutlined',
    routes: [
      { path: '/billing', redirect: '/billing/plans' },
      {
        path: '/billing/plans',
        name: 'billingPlans',
        component: './billing/plans',
      },
      {
        path: '/billing/invoices',
        name: 'billingInvoices',
        component: './billing/invoices',
      },
    ],
  },
  // 租户概览已合并进 /tenants，旧链接仍可用
  { path: '/overview', redirect: '/tenants' },
  {
    path: '/audit',
    name: 'audit',
    icon: 'SafetyCertificateOutlined',
    component: './audit',
  },
  {
    path: '/notifications',
    name: 'notifications',
    icon: 'NotificationOutlined',
    component: './notifications',
  },
  {
    path: '/services',
    name: 'services',
    icon: 'SettingOutlined',
    component: './services',
  },
  {
    path: '/moderation',
    name: 'moderation',
    icon: 'SafetyOutlined',
    component: './moderation',
  },
  {
    path: '/settings',
    name: 'settings',
    icon: 'SettingOutlined',
    component: './settings',
  },
];
