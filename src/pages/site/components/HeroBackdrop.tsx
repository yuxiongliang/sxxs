import { useEffect, useRef } from 'react';
import { useAppTheme } from '@/theme';

/**
 * Hero 科技动效背景：canvas 粒子网络（漂浮节点 + 近邻连线）。
 *
 * 三个必须遵守的工程约束：
 *   1. 尊重 prefers-reduced-motion —— 用户在系统里关了动效就只画一帧静态图；
 *   2. 页面不可见（切标签页）时停掉 rAF，别空转烧电；
 *   3. 跟随 devicePixelRatio，但上限 2，避免高分屏上白白拉满像素。
 *
 * 零依赖实现：不引 three.js / gsap，一个 canvas 足够。
 */
export default function HeroBackdrop({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { resolved } = useAppTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduceMotion = window.matchMedia?.(
      '(prefers-reduced-motion: reduce)',
    ).matches;
    const dark = resolved === 'dark';
    const dotColor = dark
      ? 'rgba(125, 211, 252, 0.85)'
      : 'rgba(22, 119, 255, 0.75)';
    const lineColor = dark ? '125, 211, 252' : '22, 119, 255';

    let width = 0;
    let height = 0;
    let raf = 0;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const points: { x: number; y: number; vx: number; vy: number }[] = [];

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const seed = () => {
      points.length = 0;
      // 密度随面积走，避免宽屏过于稀疏 / 窄屏过于拥挤
      const count = Math.round(
        Math.min(90, Math.max(28, (width * height) / 22000)),
      );
      for (let i = 0; i < count; i += 1) {
        points.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.22,
          vy: (Math.random() - 0.5) * 0.22,
        });
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const linkDistance = Math.min(160, Math.max(90, width / 12));

      for (const point of points) {
        point.x += point.vx;
        point.y += point.vy;
        if (point.x < 0 || point.x > width) point.vx *= -1;
        if (point.y < 0 || point.y > height) point.vy *= -1;
      }

      // 先画连线（在节点之下），透明度随距离衰减
      for (let i = 0; i < points.length; i += 1) {
        for (let j = i + 1; j < points.length; j += 1) {
          const dx = points[i].x - points[j].x;
          const dy = points[i].y - points[j].y;
          const distance = Math.hypot(dx, dy);
          if (distance > linkDistance) continue;
          const alpha = (1 - distance / linkDistance) * (dark ? 0.5 : 0.35);
          ctx.strokeStyle = `rgba(${lineColor}, ${alpha.toFixed(3)})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(points[i].x, points[i].y);
          ctx.lineTo(points[j].x, points[j].y);
          ctx.stroke();
        }
      }

      ctx.fillStyle = dotColor;
      for (const point of points) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const loop = () => {
      draw();
      raf = window.requestAnimationFrame(loop);
    };

    const start = () => {
      resize();
      seed();
      if (reduceMotion) {
        draw(); // 只画一帧静态网络
      } else {
        loop();
      }
    };

    const onVisibility = () => {
      if (reduceMotion) return;
      if (document.hidden) {
        window.cancelAnimationFrame(raf);
      } else {
        window.cancelAnimationFrame(raf);
        raf = window.requestAnimationFrame(loop);
      }
    };

    start();
    window.addEventListener('resize', start);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener('resize', start);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [resolved]);

  // 纯装饰：不挂 role/aria-label，无 role 的 canvas 不进入无障碍树，读屏器不会念
  return <canvas ref={canvasRef} className={className} />;
}
