/// <reference types="vitest" />
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite 配置：本地开发代理 /api 到后端，避免 CORS；生产通过 Nginx 同域
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // 只固定首屏必载的 react/antd 两大块；图表库（@ant-design/charts 及其
          // @ant-design/plots|graphs、@antv/* 依赖）不手动分包——它只被路由级
          // React.lazy 页面引用，交给 Rollup 自动拆成按需 chunk 即可。
          // 注意：不要给 charts 单独 manualChunks，其依赖树（plots/graphs）会
          // 与 antd chunk 形成静态交叉引用，把图表库又拉回首屏
          antd: ["antd", "@ant-design/icons"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    // 测试文件与源码同在 src 下，构建靠 tree-shaking 不会打进产物
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
