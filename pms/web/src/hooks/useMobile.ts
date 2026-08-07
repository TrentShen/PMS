import { useEffect, useState } from "react";

// 与 global.css 移动断点 max-width: 767px 对齐（767 及以下为移动端）；
// 不能 <= 768，否则 iPad 竖屏（768px）会渲染卡片列表但被 CSS 按桌面端 display:none，整块空白
const MOBILE_BREAKPOINT = 768;

export function useMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < MOBILE_BREAKPOINT);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return isMobile;
}
