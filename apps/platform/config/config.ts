import path from 'node:path';
import { defineConfig } from '@umijs/max';
import routes from './routes';

export default defineConfig({
  title: '赛霄玄思 SaaS 管理平台',
  hash: true,
  history: { type: 'browser' },
  antd: {},
  model: {},
  initialState: {},
  layout: {
    title: '赛霄玄思 SaaS 管理平台',
    locale: false,
  },
  locale: {
    default: 'zh-CN',
    antd: true,
    baseNavigator: true,
  },
  routes,
  // 开发期同源代理到后端；生产由 nginx 转发
  proxy: {
    '/api': { target: 'http://127.0.0.1:9000', changeOrigin: true },
  },
  alias: {
    '@shared': path.resolve(__dirname, '../../../packages/shared/src'),
  },
  // 共享包在应用根目录之外，必须显式纳入编译
  extraBabelIncludes: [path.resolve(__dirname, '../../../packages/shared')],
  mfsu: false,
  npmClient: 'npm',
});
