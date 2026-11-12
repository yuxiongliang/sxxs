import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';

/** 下发给浏览器的地图配置（后端不会返回 webKey）。 */
export interface AMapConfig {
  enabled: boolean;
  jsKey: string;
  defaultCenter: string;
  defaultZoom: number;
  useProxy: boolean;
  /** useProxy=true 时存在：JS API 安全密钥代理地址（/_AMapService） */
  serviceHost?: string;
  /** useProxy=false 时才下发，明文方式，不建议生产使用 */
  securityCode?: string;
}

export interface AMapSettingConfig {
  enabled: boolean;
  jsKey: string;
  securityCode: string;
  webKey: string;
  defaultCenter: string;
  defaultZoom: number;
  useProxy: boolean;
}

export interface AMapSetting {
  id?: number;
  category: string;
  enabled: boolean;
  config: AMapSettingConfig;
  updated_at?: string;
  // ---- 配置继承（见后端 services/setting_resolver.py）----
  source?: 'inherit' | 'override' | 'forced_inherit';
  effective_source?: string;
  platform_active?: boolean;
  policy_locked?: boolean;
  inherit_allowed?: boolean;
  masked_fields?: string[];
}

export interface AMapRegeo {
  formatted_address: string;
  province: string;
  city: string;
  district: string;
  township: string;
  street: string;
  adcode: string;
  pois: { name: string; location: string }[];
}

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

/** 读高德配置（含 webKey，仅管理端可用）。 */
export async function getAMapSetting() {
  return unwrap<AMapSetting>(request('/api/v1/settings/amap', { method: 'GET' }));
}

export async function saveAMapSetting(
  config: AMapSettingConfig | null,
  source: 'inherit' | 'override' = 'override',
) {
  // config 传 null 表示「只切换来源」：不传 config，后端保留租户原有配置，
  // 否则「跟随系统」时提交的是平台脱敏值（******），会把自己的配置毁掉。
  const data = config
    ? { source, enabled: config.enabled, config }
    : { source };
  return unwrap<AMapSetting>(
    request('/api/v1/settings/amap', { method: 'PUT', data }),
  );
}

export async function testAMapConnection() {
  return unwrap<{ success: boolean; message: string; detail?: Record<string, unknown> | null }>(
    request('/api/v1/settings/amap/test', { method: 'POST', data: {} }),
  );
}

/** 前端渲染地图用（不含 webKey）。 */
export async function getAMapFrontendConfig() {
  return unwrap<AMapConfig>(request('/api/v1/amap/config', { method: 'GET' }));
}

/** 逆地理编码：坐标 -> 地址。 */
export async function regeo(lng: number, lat: number) {
  return unwrap<AMapRegeo>(
    request('/api/v1/amap/regeo', { method: 'GET', params: { lng, lat } }),
  );
}
