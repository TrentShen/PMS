// 统一 axios 实例
// 请求拦截：自动附 Bearer token
// 响应拦截：401 时清空本地登录并跳登录页
import axios from "axios";
import { useAuth } from "@/stores/auth";

export const api = axios.create({
  baseURL: "/api",
  timeout: 10_000,
});

api.interceptors.request.use((config) => {
  const token = useAuth.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err?.response?.status === 401) {
      useAuth.getState().clear();
      if (location.pathname !== "/login") {
        location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

/** 统一格式化 axios/API 错误，优先取后端返回的 detail。 */
export function formatError(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string | { errors?: string[]; [key: string]: unknown } } }; message?: string };
  const detail = err.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (typeof detail === "object" && detail !== null && "errors" in detail && Array.isArray(detail.errors)) {
    return detail.errors.join("\n");
  }
  return err.message ?? fallback;
}
