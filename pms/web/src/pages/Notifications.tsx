// 通知中心页面（PRD 3.5）
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, List } from "antd";
import { RightOutlined } from "@ant-design/icons";
import { api } from "@/services/api";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";

interface Notify {
  id: number;
  title: string;
  content: string;
  status: string;
  created_at: string;
  // 后端 NotifyView 目前不返回跳转链接；若后续加上 url/link 字段，整行自动变为可点击
  url?: string | null;
  link?: string | null;
}

// 通知发送状态中文文案与语义色（失败→danger）
const NOTIFY_STATUS_LABEL: Record<string, string> = {
  pending: "待发送",
  sent: "已发送",
  failed: "发送失败",
  retry: "重试中",
};
const NOTIFY_STATUS_TYPE: Record<string, StatusType> = {
  pending: "warning",
  sent: "success",
  failed: "danger",
  retry: "info",
};

// 相对时间：x 分钟前 / x 小时前 / x 天前，超过 7 天显示日期
function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diffMin = Math.floor((Date.now() - t) / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} 天前`;
  return iso.replace("T", " ").slice(0, 10);
}

export default function Notifications() {
  const navigate = useNavigate();
  const [list, setList] = useState<Notify[]>([]);
  useEffect(() => {
    api.get<Notify[]>("/v1/notify/mine").then((r) => setList(r.data));
  }, []);

  return (
    <Card title="我的通知">
      {list.length === 0 ? (
        <Empty description="暂无通知" />
      ) : (
        <List
          dataSource={list}
          renderItem={(n) => {
            const link = n.url ?? n.link ?? null;
            return (
              <List.Item
                style={link ? { cursor: "pointer" } : undefined}
                onClick={link ? () => navigate(link) : undefined}
              >
                <List.Item.Meta
                  title={
                    <>
                      {n.title}{" "}
                      <StatusTag type={NOTIFY_STATUS_TYPE[n.status] ?? "default"}>
                        {NOTIFY_STATUS_LABEL[n.status] ?? n.status}
                      </StatusTag>
                    </>
                  }
                  description={n.content}
                />
                <span style={{ color: "#999", fontSize: 12, whiteSpace: "nowrap" }}>
                  {relativeTime(n.created_at)}
                  {link && <RightOutlined style={{ marginLeft: 8 }} />}
                </span>
              </List.Item>
            );
          }}
        />
      )}
    </Card>
  );
}
