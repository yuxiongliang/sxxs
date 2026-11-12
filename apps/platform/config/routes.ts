export default [
  {
    path: '/login',
    layout: false,
    component: './login',
  },
  { path: '/', redirect: '/tenants/list' },
  {
    // 租户管理：租户列表 / 套餐 / 服务类目
    // 套餐原在「计费」下，挪进来之后旧链接 /billing/plans 仍会跳过来
    path: '/tenants',
    name: 'tenantManage',
    icon: 'ClusterOutlined',
    routes: [
      { path: '/tenants', redirect: '/tenants/list' },
      {
        path: '/tenants/list',
        name: 'tenantList',
        component: './tenants',
      },
      {
        path: '/tenants/plans',
        name: 'tenantPlans',
        component: './billing/plans',
      },
      {
        path: '/tenants/categories',
        name: 'serviceCategories',
        component: './tenants/categories',
      },
    ],
  },
  {
    // 计费：只剩账单（套餐已并入「租户管理」）
    path: '/billing',
    name: 'billing',
    icon: 'WalletOutlined',
    routes: [
      { path: '/billing', redirect: '/billing/invoices' },
      { path: '/billing/plans', redirect: '/tenants/plans' },
      {
        path: '/billing/invoices',
        name: 'billingInvoices',
        component: './billing/invoices',
      },
    ],
  },
  // 租户概览已合并进租户列表，旧链接仍可用
  { path: '/overview', redirect: '/tenants/list' },
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
