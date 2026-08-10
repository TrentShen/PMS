// Vitest 全局 setup：注册 jest-dom 断言（toBeInTheDocument 等）
// 并补齐 jsdom 缺失的浏览器 API（antd 组件依赖 matchMedia）
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vitest 未开 globals，RTL 的自动 cleanup 不会生效，这里手动注册，
// 保证用例间 DOM 隔离（否则上一个用例的树会响应后续 store 变更）
afterEach(() => {
  cleanup();
});

if (!window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
