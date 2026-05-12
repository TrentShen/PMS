// 登录后的主布局：顶部栏（导航 + 当前身份）+ 页面容器
// 导航菜单按角色过滤：员工只看"首页"，Leader 多一个"下属评估"，HR 还多一个"管理台"
import { Button, Layout as AntLayout, Menu, Space, Tag, Typography } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ROLE } from "@/App";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";

const ROLE_LABEL: Record<string, string> = {
  super_admin: "超级管理员",
  hrbp: "HR",
  dept_leader: "部门 Leader",
  direct_leader: "直属上级",
  employee: "员工",
};

export default function AppLayout() {
  const user = useAuth((s) => s.user);
  const clear = useAuth((s) => s.clear);
  const navigate = useNavigate();
  const location = useLocation();

  // 构造菜单项；按角色过滤
  const menuItems = [
    { key: "/", label: "首页" },
    { key: "/history", label: "历史绩效" },
    { key: "/notifications", label: "通知" },
    { key: "/peer", label: "互评任务" },
    { key: "/anonymous", label: "匿名评价" },
    hasAnyRole(user?.role, [...ROLE.LEADER]) && { key: "/leader", label: "下属评估" },
    hasAnyRole(user?.role, [...ROLE.LEADER]) && { key: "/calibration", label: "校准" },
    // HR 管理台：hrbp/super_admin 或 has_hr_permission=true（HR 部门 Leader）
    (hasAnyRole(user?.role, [...ROLE.HR]) || user?.has_hr_permission) && { key: "/hr", label: "HR 管理台" },
    (hasAnyRole(user?.role, [...ROLE.ADMIN]) || user?.has_hr_permission) && { key: "/admin/users", label: "用户与权限" },
  ].filter(Boolean) as { key: string; label: string }[];

  // 当前激活菜单项（按 URL 前缀匹配）
  const activeKey =
    menuItems.find((m) => m.key !== "/" && location.pathname.startsWith(m.key))?.key ?? "/";

  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      <AntLayout.Header
        style={{
          background: "#fff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0 24px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Space size="large">
          <Typography.Title level={4} style={{ margin: 0 }}>
            绩效管理
          </Typography.Title>
          <Menu
            mode="horizontal"
            selectedKeys={[activeKey]}
            items={menuItems}
            onClick={(e) => navigate(e.key)}
            style={{ borderBottom: "none", minWidth: 360 }}
          />
        </Space>
        <Space>
          {user && (
            <>
              <span>{user.name}</span>
              <Tag color="blue">{ROLE_LABEL[user.role] ?? user.role}</Tag>
            </>
          )}
          <Button
            size="small"
            onClick={() => {
              clear();
              navigate("/login");
            }}
          >
            切换身份
          </Button>
        </Space>
      </AntLayout.Header>
      <AntLayout.Content style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <Outlet />
      </AntLayout.Content>
    </AntLayout>
  );
}
