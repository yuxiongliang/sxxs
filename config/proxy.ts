/**
 * @name 代理的配置
 * @see 在生产环境 代理是无法生效的，所以这里没有生产环境的配置
 * -------------------------------
 * The agent cannot take effect in the production environment
 * so there is no configuration of the production environment
 * For details, please see
 * https://pro.ant.design/docs/deploy
 *
 * @doc https://umijs.org/docs/guides/proxy
 */
export default {
  dev: {
    // 本地 FastAPI 管理端接口
    '/api/v1': {
      target: 'http://127.0.0.1:9000',
      changeOrigin: true,
    },
  },
  /**
   * @name 详细的代理配置
   * @doc https://github.com/chimurai/http-proxy-middleware
   */
  test: {
    // 与 dev 一致：指向本地 FastAPI，避免 npm run start:test 打到模板的
    // 官方演示 Worker（/api/v1/auth/login 在那里是 404）。
    '/api/v1': {
      target: 'http://127.0.0.1:9000',
      changeOrigin: true,
    },
  },
  pre: {
    '/api/': {
      target: 'your pre url',
      changeOrigin: true,
    },
  },
};
