import type { RequestOptions } from '@@/plugin-request/request';
import type { RequestConfig } from '@umijs/max';
import { getIntl, history } from '@umijs/max';
import { message, notification } from 'antd';
import { clearAccessToken } from '@/utils/authToken';
import { getFreshAccessToken } from '@/utils/refreshToken';

/** 这些端点的 401 属于业务结果（口令错误等），不该触发续期或跳登录 */
const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh'];

// 错误处理方案： 错误类型
enum ErrorShowType {
  SILENT = 0,
  WARN_MESSAGE = 1,
  ERROR_MESSAGE = 2,
  NOTIFICATION = 3,
  REDIRECT = 9,
}
// 与后端约定的响应数据格式
interface ResponseStructure {
  success: boolean;
  data: unknown;
  errorCode?: number;
  errorMessage?: string;
  showType?: ErrorShowType;
}

/**
 * @name 错误处理
 * pro 自带的错误处理， 可以在这里做自己的改动
 * @doc https://umijs.org/docs/max/request#配置
 */
export const errorConfig: RequestConfig = {
  // 错误处理： umi@3 的错误处理方案。
  errorConfig: {
    // 错误抛出
    errorThrower: (res) => {
      const { success, data, errorCode, errorMessage, showType } =
        res as ResponseStructure;
      if (!success) {
        const error: any = new Error(errorMessage);
        error.name = 'BizError';
        error.info = { errorCode, errorMessage, showType, data };
        throw error; // 抛出自制的错误
      }
    },
    // 错误接收及处理
    errorHandler: (error: any, opts: any) => {
      if (opts?.skipErrorHandler) throw error;
      // 我们的 errorThrower 抛出的错误。
      if (error.name === 'BizError') {
        const errorInfo: ResponseStructure | undefined = error.info;
        if (errorInfo) {
          const { errorMessage, errorCode } = errorInfo;
          switch (errorInfo.showType) {
            case ErrorShowType.SILENT:
              // do nothing
              break;
            case ErrorShowType.WARN_MESSAGE:
              message.warning(errorMessage);
              break;
            case ErrorShowType.ERROR_MESSAGE:
              message.error(errorMessage);
              break;
            case ErrorShowType.NOTIFICATION:
              notification.open({
                title: errorCode,
                description: errorMessage,
              });
              break;
            case ErrorShowType.REDIRECT:
              history.replace('/user/login');
              break;
            default:
              message.error(errorMessage);
          }
        }
      } else if (error.response) {
        // Axios 的错误：请求已发出、服务端也响应了，但状态码超出 2xx
        const status: number = error.response.status;
        const url: string = opts?.url ?? error.config?.url ?? '';
        const isAuthEndpoint = AUTH_ENDPOINTS.some((path) =>
          url.includes(path),
        );

        // 401：请求拦截器已经会提前续期，走到这里说明续期后仍无效
        // （refresh token 过期 / 被吊销 / 账号停用）→ 清理态并回登录页
        if (status === 401 && !isAuthEndpoint) {
          clearAccessToken();
          const { pathname, search, hash } = history.location;
          // 公开落地页允许匿名浏览：这里只清 token，不强行跳登录
          // 公开页（站点根与产品介绍页）允许匿名浏览：只清 token，不强行跳登录
          const isPublicPage =
            pathname === '/' ||
            pathname === '/site' ||
            pathname.startsWith('/products') ||
            pathname === '/user/login';
          if (!isPublicPage) {
            message.warning(
              getIntl().formatMessage({
                id: 'app.request.sessionExpired',
                defaultMessage: '登录已过期，请重新登录',
              }),
            );
            history.replace(
              `/user/login?redirect=${encodeURIComponent(pathname + search + hash)}`,
            );
          }
          return;
        }

        message.error(`Response status:${status}`);
      } else if (typeof navigator !== 'undefined' && !navigator.onLine) {
        message.error(
          getIntl().formatMessage({
            id: 'app.request.offline',
            defaultMessage:
              'Network unavailable. Please check your connection and try again.',
          }),
        );
      } else if (error.request) {
        message.error('None response! Please retry.');
      } else {
        message.error('Request error, please retry.');
      }
    },
  },

  // 请求拦截器
  requestInterceptors: [
    // 异步拦截器：token 快过期时先静默续期再发请求，
    // 这样「切回标签页触发 refetch」不会再因为过期 token 报 401。
    async (config: RequestOptions) => {
      const token = await getFreshAccessToken();
      if (token) {
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${token}`,
        };
      }
      return config;
    },
  ],

  // 响应拦截器
  responseInterceptors: [],
};
