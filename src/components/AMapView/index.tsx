import { useEffect, useRef, useState } from 'react';
import type { AMapConfig } from '@/services/amap/api';

declare global {
  interface Window {
    AMap?: any;
    _AMapSecurityConfig?: Record<string, string>;
  }
}

let loader: Promise<any> | null = null;

/**
 * 按需加载高德 JS API 2.0。
 *
 * 关键顺序：window._AMapSecurityConfig 必须在 <script> 插入**之前**赋值，
 * 之后再设置无效（高德官方明确要求）。
 */
function loadAMap(config: AMapConfig): Promise<any> {
  if (window.AMap) return Promise.resolve(window.AMap);
  if (loader) return loader;
  loader = new Promise((resolve, reject) => {
    if (!config.jsKey) {
      reject(new Error('未配置高德 Web端(JS API) key'));
      return;
    }
    window._AMapSecurityConfig = config.useProxy
      ? { serviceHost: config.serviceHost ?? '' }
      : { securityJsCode: config.securityCode ?? '' };
    const script = document.createElement('script');
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${config.jsKey}`;
    script.async = true;
    script.onload = () =>
      window.AMap ? resolve(window.AMap) : reject(new Error('AMap 未挂载'));
    script.onerror = () =>
      reject(new Error('高德 JS API 脚本加载失败（检查 key 与域名白名单）'));
    document.head.appendChild(script);
  });
  return loader;
}

export interface AMapViewProps {
  config: AMapConfig;
  height?: number;
  /** 点击地图回调，返回高德坐标（GCJ-02） */
  onPick?: (lng: number, lat: number) => void;
}

export default function AMapView({
  config,
  height = 320,
  onPick,
}: AMapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let disposed = false;
    loadAMap(config)
      .then((AMap) => {
        if (disposed || !containerRef.current) return;
        const [lng, lat] = (config.defaultCenter || '116.397428,39.90923')
          .split(',')
          .map((item) => Number(item.trim()));
        const map = new AMap.Map(containerRef.current, {
          zoom: config.defaultZoom || 11,
          center: [lng, lat],
        });
        mapRef.current = map;
        if (onPick) {
          map.on('click', (event: any) => {
            const position = [event.lnglat.getLng(), event.lnglat.getLat()];
            if (!markerRef.current) {
              markerRef.current = new AMap.Marker({ position, map });
            } else {
              markerRef.current.setPosition(position);
            }
            onPick(position[0], position[1]);
          });
        }
      })
      .catch((err: Error) => setError(err.message));
    return () => {
      disposed = true;
      mapRef.current?.destroy?.();
      mapRef.current = null;
      markerRef.current = null;
    };
    // config 变化时重建地图（key / 中心点切换）
  }, [config.jsKey, config.useProxy, config.serviceHost, config.securityCode]);

  if (error) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px dashed #d9d9d9',
          borderRadius: 8,
          color: '#999',
          padding: 16,
          textAlign: 'center',
        }}
      >
        {error}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ height, width: '100%', borderRadius: 8 }}
    />
  );
}
