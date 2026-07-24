import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "antd/dist/reset.css";
import "./global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* 主题令牌与设计令牌（styles/tokens.css）对齐 */}
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#3370FF",
          colorSuccess: "#00B42A",
          colorWarning: "#FF7D00",
          colorError: "#F53F3F",
          colorText: "#1F2329",
          colorTextSecondary: "#646A73",
          colorTextTertiary: "#6B7280",
          colorBorder: "#DEE0E3",
          colorBgLayout: "#F5F6F7",
          colorBgContainer: "#FFFFFF",
          borderRadius: 8,
          fontSize: 14,
          controlHeight: 32,
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
