// 主布局：桌面端左侧边栏 + 顶部栏（Linear 结构），移动端抽屉侧边栏
// 断点：≤1023px 侧边栏隐藏，汉堡按钮 + Drawer 替代（样式见 global.css）
import { useState } from "react";
import { Button, Drawer, Layout as AntLayout, Menu, Modal, Space, Tag, message } from "antd";
import { ArrowLeftOutlined, MenuOutlined, SwapOutlined } from "@ant-design/icons";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ROLE } from "@/App";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { api, formatError } from "@/services/api";


const ROLE_LABEL: Record<string, string> = {
  super_admin: "超级管理员",
  hrbp: "HR",
  dept_leader: "部门 Leader",
  direct_leader: "直属上级",
  employee: "员工",
};

// 深层路由（详情页等不在菜单中的页面）→ 顶栏标题，按前缀匹配，顺序即优先级
const PATH_TITLE: [string, string][] = [
  ["/self/", "绩效自评"],
  ["/objectives/", "目标制定"],
  ["/objective-cycles", "目标周期"],
  ["/leader", "下属评估"],
  ["/calibration", "绩效校准"],
  ["/feedback", "绩效反馈"],
  ["/probation/", "试用期详情"],
  ["/probation", "试用期管理"],
  ["/trend", "绩效趋势"],
  ["/hr/dashboard", "绩效看板"],
  ["/hr", "HR 管理台"],
  ["/admin/users", "用户与权限"],
];

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
    (hasAnyRole(user?.role, ["dept_leader", ...ROLE.HR]) || user?.has_hr_permission) && { key: "/calibration", label: "校准" },
    (hasAnyRole(user?.role, [...ROLE.HR, ...ROLE.LEADER]) || user?.has_hr_permission) && { key: "/probation", label: "试用期管理" },
    (hasAnyRole(user?.role, [...ROLE.HR]) || user?.has_hr_permission) && { key: "/hr", label: "HR 管理台" },
    (hasAnyRole(user?.role, [...ROLE.HR]) || user?.has_hr_permission) && { key: "/objective-cycles", label: "目标周期" },
    (hasAnyRole(user?.role, [...ROLE.HR]) || user?.has_hr_permission) && { key: "/hr/dashboard", label: "绩效看板" },
    (hasAnyRole(user?.role, [...ROLE.ADMIN]) || user?.has_hr_permission) && { key: "/admin/users", label: "用户与权限" },
  ].filter(Boolean) as { key: string; label: string }[];

  const activeKey =
    menuItems.find((m) => m.key !== "/" && location.pathname.startsWith(m.key))?.key ?? "/";
  const pageTitle =
    PATH_TITLE.find(([prefix]) => location.pathname.startsWith(prefix))?.[1] ??
    menuItems.find((m) => m.key === activeKey)?.label ??
    "绩效管理";
  // 路径段数 >1 视为详情/深层页面（如 /self/1、/leader/2/users/3），顶栏左侧显示返回按钮
  const isDetailPage = location.pathname.split("/").filter(Boolean).length > 1;

  function onMenuClick(key: string) {
    navigate(key);
    setDrawerOpen(false);
  }

  function logout() {
    clear();
    navigate("/login");
  }

  const roleSwitchButton = user?.switchable_roles && user.switchable_roles.length > 0 && (
    <Button
      size="small"
      icon={<SwapOutlined />}
      loading={switching}
      onClick={() => {
        Modal.confirm({
          title: "切换角色",
          content: (
            <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
              {user.switchable_roles!.map((r) => (
                <Button
                  key={r}
                  type={r === user.role ? "primary" : "default"}
                  block
                  disabled={r === user.role}
                  onClick={async () => {
                    if (r === user.role) return;
                    setSwitching(true);
                    try {
                      const res = await api.post("/v1/auth/switch-role", { role: r });
                      const { token, user: newUser } = res.data;
                      setToken(token);
                      setUser(newUser);
                      message.success(`已切换为 ${ROLE_LABEL[r] ?? r}`);
                      Modal.destroyAll();
                    } catch (e) {
                      message.error(formatError(e, "切换失败"));
                    } finally {
                      setSwitching(false);
                    }
                  }}
                >
                  {ROLE_LABEL[r] ?? r}
                  {r === user.role ? "（当前）" : ""}
                </Button>
              ))}
            </Space>
          ),
          icon: null,
          okButtonProps: { style: { display: "none" } },
          cancelText: "取消",
        });
      }}
    >
      切换角色
    </Button>
  );

  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      {/* 桌面端左侧边栏（≤1023px 由 CSS 隐藏，改用抽屉） */}
      <AntLayout.Sider className="pms-sider" width={240} breakpoint="lg" collapsedWidth={0} trigger={null}>
        <div className="pms-sider-logo">
          <h4>绩效管理</h4>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={(e) => navigate(e.key)}
        />
      </AntLayout.Sider>

      <AntLayout>
        {/* 顶部全局栏 */}
        <AntLayout.Header className="pms-topbar">
          <div className="pms-topbar-left">
            {/* 详情/深层页面：返回按钮（移动端/桌面均显示）；一级页面：移动端/平板汉堡按钮 */}
            {isDetailPage ? (
              <Button
                type="text"
                aria-label="返回"
                icon={<ArrowLeftOutlined />}
                onClick={() => navigate(-1)}
              />
            ) : (
              <Button
                className="pms-menu-trigger"
                type="text"
                aria-label="打开菜单"
                icon={<MenuOutlined />}
                onClick={() => setDrawerOpen(true)}
              />
            )}
            <span className="pms-page-title">{pageTitle}</span>
          </div>
          <Space className="pms-topbar-right">
            {user && (
              <>
                <span className="pms-user-name">{user.name}</span>
                <Tag color="blue">{ROLE_LABEL[user.role] ?? user.role}</Tag>
                {roleSwitchButton}
              </>
            )}
            <Button size="small" onClick={logout}>
              退出登录
            </Button>
          </Space>
        </AntLayout.Header>

        <AntLayout.Content>
          <div className="pms-content">
            <Outlet />
          </div>
        </AntLayout.Content>
      </AntLayout>

      {/* 移动端侧边抽屉 */}
      <Drawer
        title={
          <Space>
            <span>{user?.name}</span>
            <Tag color="blue">{ROLE_LABEL[user?.role ?? ""] ?? ""}</Tag>
            {user?.switchable_roles && user.switchable_roles.length > 0 && (
              <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
                可切换角色
              </span>
            )}
          </Space>
        }
        placement="left"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={280}
        styles={{ body: { padding: 0 } }}
      >
        <Menu
          mode="vertical"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={(e) => onMenuClick(e.key)}
          style={{ borderRight: "none" }}
        />
        <div style={{ padding: "16px 24px", borderTop: "1px solid var(--color-border)" }}>
          <Button block onClick={() => { logout(); setDrawerOpen(false); }}>
            退出登录
          </Button>
        </div>
      </Drawer>
    </AntLayout>
  );
}
