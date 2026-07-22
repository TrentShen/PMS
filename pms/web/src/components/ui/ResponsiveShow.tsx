// 响应式显隐：集中管理桌面/移动端显隐，避免散落媒体查询
// mobile = ≤767px（与 global.css 断点一致）
interface ResponsiveShowProps {
  on: "mobile" | "desktop";
  children: React.ReactNode;
}

const ResponsiveShow: React.FC<ResponsiveShowProps> = ({ on, children }) => (
  <div className={on === "mobile" ? "pms-mobile-only" : "pms-desktop-only"}>{children}</div>
);

export default ResponsiveShow;
