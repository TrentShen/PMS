// 语义化状态标签：统一各页面状态展示，避免散落的 Tag color 魔法字符串
import { Tag } from "antd";

export type StatusType = "success" | "warning" | "danger" | "info" | "primary" | "default";

const COLOR_MAP: Record<StatusType, string> = {
  success: "success",
  warning: "warning",
  danger: "error",
  info: "processing",
  primary: "blue",
  default: "default",
};

interface StatusTagProps {
  type?: StatusType;
  children: React.ReactNode;
}

const StatusTag: React.FC<StatusTagProps> = ({ type = "default", children }) => (
  <Tag color={COLOR_MAP[type]} style={{ marginInlineEnd: 0 }}>
    {children}
  </Tag>
);

export default StatusTag;
