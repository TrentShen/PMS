// 移动端底部 Tab 导航（仅 ≤767px 显示，样式见 global.css 末尾）
// 对齐飞书/企微移动应用习惯：首页 / 待办 / 通知 三个高频入口，待办带角标
import { Badge } from "antd";
import { BellOutlined, HomeOutlined, TeamOutlined } from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";

interface MobileTabBarProps {
  /** 待办角标数：评估任务 + 目标制定 + 待互评任务 */
  todoCount: number;
}

export default function MobileTabBar({ todoCount }: MobileTabBarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  // 通知接口（/v1/notify/mine）返回的是发送状态而非已读状态，无未读数字段，故通知 Tab 不显示角标
  const tabs = [
    { key: "/", label: "首页", icon: <HomeOutlined />, badge: 0 },
    { key: "/peer", label: "待办", icon: <TeamOutlined />, badge: todoCount },
    { key: "/notifications", label: "通知", icon: <BellOutlined />, badge: 0 },
  ];

  return (
    <nav className="pms-mobile-tabbar" aria-label="底部导航">
      {tabs.map((t) => {
        const active =
          t.key === "/" ? location.pathname === "/" : location.pathname.startsWith(t.key);
        return (
          <button
            key={t.key}
            type="button"
            className={`pms-mobile-tab${active ? " pms-mobile-tab-active" : ""}`}
            aria-current={active ? "page" : undefined}
            onClick={() => navigate(t.key)}
          >
            <Badge count={t.badge} size="small">
              <span className="pms-mobile-tab-icon">{t.icon}</span>
            </Badge>
            <span className="pms-mobile-tab-label">{t.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
