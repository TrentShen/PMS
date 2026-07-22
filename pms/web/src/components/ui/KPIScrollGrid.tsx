// 移动端 KPI 横向滑动网格：scroll-snap 对齐，卡片最小宽 160px
// 桌面端配合 ResponsiveShow 隐藏，或直接在 ≤639px 使用
interface KPIScrollGridProps {
  children: React.ReactNode;
}

const KPIScrollGrid: React.FC<KPIScrollGridProps> = ({ children }) => (
  <div className="kpi-grid-scroll">{children}</div>
);

export default KPIScrollGrid;
