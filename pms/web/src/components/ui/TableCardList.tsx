// 移动端表格卡片列表：与桌面 antd Table 并存，≤767px 由 CSS 自动切换
// 用法：桌面 Table 外包一层 className="pms-responsive-table"，移动端渲染本组件
import { Empty, Spin } from "antd";

export interface CardColumn<T> {
  title: React.ReactNode;
  dataIndex?: keyof T & string;
  render?: (record: T) => React.ReactNode;
}

interface TableCardListProps<T> {
  columns: CardColumn<T>[];
  dataSource: T[];
  rowKey: (record: T) => React.Key;
  /** 加载中：显示 Spin，避免加载期闪现空态 */
  loading?: boolean;
  /** 空数据提示文案（默认"暂无数据"） */
  emptyText?: string;
  /** 卡片底部操作区 */
  renderActions?: (record: T) => React.ReactNode;
  /** 点击卡片 */
  onCardClick?: (record: T) => void;
}

function TableCardList<T>({ columns, dataSource, rowKey, loading, emptyText, renderActions, onCardClick }: TableCardListProps<T>) {
  if (loading) {
    return (
      <div className="table-card-list" style={{ textAlign: "center", padding: "var(--space-7) 0" }}>
        <Spin />
      </div>
    );
  }
  if (dataSource.length === 0) {
    return (
      <div className="table-card-list">
        <Empty description={emptyText ?? "暂无数据"} />
      </div>
    );
  }
  return (
    <div className="table-card-list">
      {dataSource.map((record) => (
        <div
          key={rowKey(record)}
          className="table-card"
          role={onCardClick ? "button" : undefined}
          tabIndex={onCardClick ? 0 : undefined}
          onClick={onCardClick ? () => onCardClick(record) : undefined}
          onKeyDown={
            onCardClick
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") onCardClick(record);
                }
              : undefined
          }
        >
          {columns.map((col, i) => (
            <div className="table-card-row" key={i}>
              <span className="table-card-label">{col.title}</span>
              <span className="table-card-value">
                {col.render
                  ? col.render(record)
                  : col.dataIndex
                    ? String(record[col.dataIndex] ?? "-")
                    : "-"}
              </span>
            </div>
          ))}
          {/* 阻止冒泡：操作按钮点击不应触发卡片自身的 onCardClick 跳转 */}
          {renderActions && (
            <div className="table-card-actions" onClick={(e) => e.stopPropagation()}>
              {renderActions(record)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default TableCardList;
