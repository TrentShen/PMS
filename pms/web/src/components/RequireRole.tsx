// 角色守卫：未命中角色时重定向到首页或显示提示
// 用法：
//   <Route element={<RequireRole roles={["hrbp", "super_admin"]} />}>
//     <Route path="/hr" element={<HrConsole />} />
//   </Route>
import { Navigate, Outlet } from "react-router-dom";
import { Result } from "antd";
import { useAuth } from "@/stores/auth";

interface Props {
  roles: string[];
  // 可选：命中失败时的渲染策略。默认重定向回首页；传 "forbid" 则显示 403
  fallback?: "redirect" | "forbid";
  // 允许 has_hr_permission=true 的用户通过（HR 部门 Leader 场景）
  allowHrPermission?: boolean;
  // 允许有下属的用户通过（任意层级的上级都能进"下属评估"）
  allowHasSubordinates?: boolean;
}

export default function RequireRole({ roles, fallback = "redirect", allowHrPermission = false, allowHasSubordinates = false }: Props) {
  const user = useAuth((s) => s.user);

  if (!user) return <Navigate to="/login" replace />;

  const allowed = roles.includes(user.role)
    || (allowHrPermission && user.has_hr_permission)
    || (allowHasSubordinates && user.has_subordinates);

  if (!allowed) {
    if (fallback === "forbid") {
      return (
        <Result
          status="403"
          title="403"
          subTitle={`你的角色是「${user.role}」，无权访问此页面`}
        />
      );
    }
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}


// 工具函数：判断当前用户是否命中任一角色（用于菜单按钮级显示）
export function hasAnyRole(userRole: string | undefined, roles: string[]): boolean {
  if (!userRole) return false;
  return roles.includes(userRole);
}
