import { createStyles } from 'antd-style';

/** 落地页样式：全部走 antd token，暗色下自动跟随，无需写两套颜色 */
export default createStyles(({ token, css }) => ({
  shell: css`
    min-height: 100vh;
    background: ${token.colorBgLayout};
    color: ${token.colorText};
    transition: background 0.2s ease, color 0.2s ease;
  `,
  container: css`
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 32px;
  `,
  header: css`
    position: sticky;
    top: 0;
    z-index: 20;
    backdrop-filter: saturate(180%) blur(12px);
    background: ${token.colorBgContainer}dd;
    border-bottom: 1px solid ${token.colorBorderSecondary};
  `,
  headerInner: css`
    display: flex;
    align-items: center;
    gap: 28px;
    height: 64px;
  `,
  brand: css`
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 700;
    color: ${token.colorText};
    white-space: nowrap;
    text-decoration: none;
  `,
  nav: css`
    display: flex;
    align-items: center;
    gap: 4px;
  `,
  navButton: css`
    height: 34px;
    padding: 0 12px;
    border-radius: ${token.borderRadius}px;
    border: none;
    background: transparent;
    color: ${token.colorTextSecondary};
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
    &:hover {
      color: ${token.colorPrimary};
      background: ${token.colorFillTertiary};
    }
  `,
  actions: css`
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  `,
  searchTrigger: css`
    display: flex;
    align-items: center;
    gap: 8px;
    height: 34px;
    padding: 0 10px;
    min-width: 168px;
    border-radius: ${token.borderRadius}px;
    border: 1px solid ${token.colorBorder};
    background: ${token.colorFillQuaternary};
    color: ${token.colorTextTertiary};
    font-size: 13px;
    cursor: pointer;
    &:hover {
      border-color: ${token.colorPrimary};
      color: ${token.colorTextSecondary};
    }
  `,
  kbd: css`
    margin-left: auto;
    padding: 1px 5px;
    border-radius: 4px;
    border: 1px solid ${token.colorBorderSecondary};
    font-size: 11px;
    font-family: ${token.fontFamilyCode};
    color: ${token.colorTextTertiary};
  `,
  hero: css`
    position: relative;
    overflow: hidden;
    padding: 96px 0 72px;
    text-align: center;
    background: radial-gradient(120% 90% at 50% 0%, ${token.colorPrimaryBg} 0%, transparent 62%);
  `,
  badge: css`
    display: inline-block;
    margin-bottom: 12px;
    padding: 4px 12px;
    border-radius: 999px;
    border: 1px solid ${token.colorPrimaryBorder};
    background: ${token.colorPrimaryBg};
    color: ${token.colorPrimary};
    font-size: 13px;
  `,
  heroTitle: css`
    margin: 0 0 16px;
    font-size: 56px;
    line-height: 1.15;
    letter-spacing: -0.5px;
  `,
  heroSubtitle: css`
    max-width: 720px;
    margin: 0 auto 32px;
    color: ${token.colorTextSecondary};
    font-size: 16px;
    line-height: 1.8;
  `,
  section: css`
    padding: 72px 0;
  `,
  sectionHead: css`
    margin-bottom: 36px;
    text-align: center;
  `,
  sectionTitle: css`
    margin: 0 0 8px;
    font-size: 32px;
  `,
  sectionSubtitle: css`
    margin: 0;
    color: ${token.colorTextSecondary};
  `,
  statValue: css`
    font-size: 34px;
    font-weight: 700;
    color: ${token.colorPrimary};
  `,
  statLabel: css`
    color: ${token.colorTextSecondary};
    font-size: 13px;
  `,
  cardTitle: css`
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-weight: 600;
  `,
  cardDesc: css`
    margin: 0;
    color: ${token.colorTextSecondary};
    font-size: 13px;
    line-height: 1.7;
  `,
  moduleItem: css`
    display: flex;
    align-items: center;
    gap: 8px;
    height: 44px;
    padding: 0 14px;
    border-radius: ${token.borderRadius}px;
    border: 1px solid ${token.colorBorderSecondary};
    background: ${token.colorBgContainer};
    color: ${token.colorText};
    font-size: 14px;
    text-decoration: none;
    transition: all 0.15s ease;
    &:hover {
      border-color: ${token.colorPrimary};
      color: ${token.colorPrimary};
    }
  `,
  footer: css`
    margin-top: 48px;
    padding: 48px 0 32px;
    border-top: 1px solid ${token.colorBorderSecondary};
    background: ${token.colorBgContainer};
  `,
  footerColTitle: css`
    margin-bottom: 12px;
    font-weight: 600;
    font-size: 13px;
  `,
  footerLink: css`
    display: block;
    margin-bottom: 8px;
    color: ${token.colorTextSecondary};
    font-size: 13px;
    text-decoration: none;
    &:hover {
      color: ${token.colorPrimary};
    }
  `,
  footerBottom: css`
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 32px;
    padding-top: 20px;
    border-top: 1px solid ${token.colorBorderSecondary};
    color: ${token.colorTextTertiary};
    font-size: 12px;
  `,
  heroBackdrop: css`
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
    pointer-events: none;
  `,
  heroGrid: css`
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image: linear-gradient(
        to right,
        ${token.colorBorderSecondary} 1px,
        transparent 1px
      ),
      linear-gradient(to bottom, ${token.colorBorderSecondary} 1px, transparent 1px);
    background-size: 56px 56px;
    opacity: 0.5;
    mask-image: radial-gradient(ellipse 70% 60% at 50% 0%, #000 30%, transparent 78%);
    animation: siteGridDrift 26s linear infinite;
    @keyframes siteGridDrift {
      from {
        background-position: 0 0, 0 0;
      }
      to {
        background-position: 56px 56px, 56px 56px;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      animation: none;
    }
  `,
  heroGlow: css`
    position: absolute;
    left: 50%;
    top: -18%;
    width: 760px;
    height: 760px;
    transform: translateX(-50%);
    pointer-events: none;
    background: radial-gradient(circle, ${token.colorPrimaryBg} 0%, transparent 66%);
    opacity: 0.9;
    animation: siteGlowPulse 7s ease-in-out infinite;
    @keyframes siteGlowPulse {
      0%,
      100% {
        opacity: 0.55;
        transform: translateX(-50%) scale(1);
      }
      50% {
        opacity: 0.95;
        transform: translateX(-50%) scale(1.08);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      animation: none;
    }
  `,
  heroContent: css`
    position: relative;
    z-index: 1;
  `,
  // 打字机容器：必须是**块级** flex —— 用 inline-flex 会和上面 inline-block 的
  // 徽章排在同一行（之前 h1 是块级元素，天然换行，加包裹层时要显式保留）。
  // 块级 + justify-content:center 仍然让「文字 + 光标」居中并紧挨着。
  // min-height 防止文字逐个出现时整段 hero 上下抖动。
  heroTitleWrap: css`
    // 字号用变量统一驱动：标题与光标都读它，改一处即可整体缩放
    --hero-title-size: clamp(56px, 5.4vw, 80px);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    // 上下留白，把标题从徽章与副标题之间「托」出来
    margin: 18px 0 34px;
    // 高度跟字号走：打字过程中文字为空时也不会塌陷抖动
    min-height: calc(var(--hero-title-size) * 1.2);
  `,
  heroTitleTyping: css`
    margin: 0;
    font-size: var(--hero-title-size);
    line-height: 1.15;
    letter-spacing: -0.5px;
    font-weight: 800;
    background: linear-gradient(
      100deg,
      ${token.colorPrimary} 0%,
      ${token.colorPrimaryHover} 22%,
      ${token.colorText} 44%,
      ${token.colorPrimary} 68%,
      ${token.colorPrimaryHover} 100%
    );
    background-size: 260% auto;
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    // 逐个出现本身就是「揭示」，所以这里只保留扫光，不再叠加 clip-path 揭幕
    animation: siteShimmer 7s linear infinite;
    @keyframes siteShimmer {
      from {
        background-position: 0% 50%;
      }
      to {
        background-position: 260% 50%;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      animation: none;
      background-position: 0% 50%;
    }
  `,
  // 光标：方块 + 光晕，打字时呼吸闪烁
  caret: css`
    display: inline-block;
    width: calc(var(--hero-title-size) * 0.06);
    height: calc(var(--hero-title-size) * 0.92);
    border-radius: 2px;
    background: ${token.colorPrimary};
    box-shadow: 0 0 12px ${token.colorPrimary};
    animation: siteCaretBlink 1s steps(1, end) infinite;
    @keyframes siteCaretBlink {
      0%,
      49% {
        opacity: 1;
      }
      50%,
      100% {
        opacity: 0;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      animation: none;
    }
  `,
  heroFadeUp: css`
    opacity: 0;
    transform: translateY(14px);
    animation: siteFadeUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    @keyframes siteFadeUp {
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      opacity: 1;
      transform: none;
      animation: none;
    }
  `,
}));
