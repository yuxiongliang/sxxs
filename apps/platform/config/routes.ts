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
