// 路由守卫：未登录跳 /login
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/stores/auth";

export default function ProtectedRoute() {
  const token = useAuth((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}
