// 主布局：PC 端顶部导航，移动端抽屉侧边栏
import { useState } from "react";
import { Button, Drawer, Dropdown, Layout as AntLayout, Menu, Space, Tag, Typography, message } from "antd";
import { MenuOutlined, SwapOutlined } from "@ant-design/icons";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ROLE } from "@/App";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { api } from "@/services/api";

const ROLE_LABEL: Record<string, string> = {
  super_admin: "超级管理员",
  hrbp: "HR",
  dept_leader: "部门 Leader",
  direct_leader: "直属上级",
  employee: "员工",
};

export default function AppLayout() {
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const setToken = useAuth((s) => s.setToken);
  const clear = useAuth((s) => s.clear);
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  // 菜单/入口权限基于当前生效角色（role），切换角色后菜单同步变化

  // 构造菜单项；按角色过滤
  const menuItems = [
    { key: "/", label: "首页" },
    { key: "/history", label: "历史绩效" },
    { key: "/notifications", label: "通知" },
    { key: "/peer", label: "互评任务" },
    { key: "/anonymous", label: "匿名评价" },
    hasAnyRole(user?.role, [...ROLE.LEADER]) && { key: "/leader", label: "下属评估" },
    hasAnyRole(user?.role, [...ROLE.LEADER]) && { key: "/calibration", label: "校准" },
    (hasAnyRole(user?.role, [...ROLE.HR, ...ROLE.LEADER]) || user?.has_hr_permission) && { key: "/probation", label: "试用期管理" },
    (hasAnyRole(user?.role, [...ROLE.HR]) || user?.has_hr_permission) && { key: "/hr", label: "HR 管理台" },
    (hasAnyRole(user?.role, [...ROLE.ADMIN]) || user?.has_hr_permission) && { key: "/admin/users", label: "用户与权限" },
  ].filter(Boolean) as { key: string; label: string }[];

  const activeKey =
    menuItems.find((m) => m.key !== "/" && location.pathname.startsWith(m.key))?.key ?? "/";

  function onMenuClick(key: string) {
    navigate(key);
    setDrawerOpen(false);
  }

  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      {/* PC 端顶部导航 */}
      <AntLayout.Header className="pms-header">
        <Space size="large" className="pms-header-left">
          {/* 移动端汉堡按钮 */}
          <Button
            className="pms-menu-trigger"
            type="text"
            icon={<MenuOutlined />}
            onClick={() => setDrawerOpen(true)}
          />
          <Typography.Title level={4} style={{ margin: 0, whiteSpace: "nowrap" }}>
            绩效管理
          </Typography.Title>
          {/* PC 端横向菜单 */}
          <Menu
            className="pms-desktop-menu"
            mode="horizontal"
            selectedKeys={[activeKey]}
            items={menuItems}
            onClick={(e) => navigate(e.key)}
            style={{ borderBottom: "none", minWidth: 360 }}
          />
        </Space>
        <Space className="pms-header-right">
          {user && (
            <>
              <span className="pms-user-name">{user.name}</span>
              <Tag color="blue">{ROLE_LABEL[user.role] ?? user.role}</Tag>
              {user.switchable_roles && user.switchable_roles.length > 0 && (
                <Dropdown
                  menu={{
                    items: user.switchable_roles.map((r) => ({
                      key: r,
                      label: ROLE_LABEL[r] ?? r,
                      disabled: r === user.role,
                    })),
                    onClick: async ({ key }) => {
                      if (key === user.role) return;
                      setSwitching(true);
                      try {
                        const res = await api.post("/v1/auth/switch-role", { role: key });
                        const { token, user: newUser } = res.data;
                        setToken(token);
                        setUser(newUser);
                        message.success(`已切换为 ${ROLE_LABEL[key] ?? key}`);
                        navigate(0);
                      } catch (e: any) {
                        message.error(e?.response?.data?.detail || "切换失败");
                      } finally {
                        setSwitching(false);
                      }
                    },
                  }}
                >
                  <Button size="small" icon={<SwapOutlined />} loading={switching}>
                    切换角色
                  </Button>
                </Dropdown>
              )}
            </>
          )}
          <Button
            size="small"
            onClick={() => { clear(); navigate("/login"); }}
          >
            退出登录
          </Button>
        </Space>
      </AntLayout.Header>

      {/* 移动端侧边抽屉 */}
      <Drawer
        title={
          <Space>
            <span>{user?.name}</span>
            <Tag color="blue">{ROLE_LABEL[user?.role ?? ""] ?? ""}</Tag>
            {user?.switchable_roles && user.switchable_roles.length > 0 && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                可切换角色
              </Typography.Text>
            )}
          </Space>
        }
        placement="left"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={260}
        styles={{ body: { padding: 0 } }}
      >
        <Menu
          mode="vertical"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={(e) => onMenuClick(e.key)}
          style={{ borderRight: "none" }}
        />
        <div style={{ padding: "16px 24px", borderTop: "1px solid #f0f0f0" }}>
          <Button
            block
            onClick={() => { clear(); navigate("/login"); setDrawerOpen(false); }}
          >
            退出登录
          </Button>
        </div>
      </Drawer>

      <AntLayout.Content style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <Outlet />
      </AntLayout.Content>
    </AntLayout>
  );
}
