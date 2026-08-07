// 路由守卫：未登录跳 /login，带上原路径便于登录后回跳
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/stores/auth";

export default function ProtectedRoute() {
  const token = useAuth((s) => s.token);
  const location = useLocation();
  if (!token) {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  return <Outlet />;
}
