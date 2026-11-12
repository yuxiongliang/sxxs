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
    path: '/users',
    name: 'platformUsers',
    icon: 'TeamOutlined',
    component: './users',
  },
  {
    // 总部财务：下面分「SAAS 财务」（账单 / 抽佣台账）
    path: '/billing',
    name: 'billing',
    icon: 'WalletOutlined',
    routes: [
      { path: '/billing', redirect: '/billing/saas/invoices' },
      // 旧链接兼容
      { path: '/billing/plans', redirect: '/tenants/plans' },
      { path: '/billing/invoices', redirect: '/billing/saas/invoices' },
      { path: '/billing/commission', redirect: '/billing/saas/commission' },
      {
        path: '/billing/saas',
        name: 'billingSaas',
        routes: [
          { path: '/billing/saas', redirect: '/billing/saas/invoices' },
          {
            path: '/billing/saas/invoices',
            name: 'billingInvoices',
            component: './billing/invoices',
          },
          {
            path: '/billing/saas/commission',
            name: 'billingCommission',
            component: './billing/commission',
          },
        ],
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
