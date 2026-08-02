// 通知中心页面（PRD 3.5）
import { useEffect, useState } from "react";
import { Card, Empty, List } from "antd";
import { api } from "@/services/api";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";

interface Notify {
  id: number;
  title: string;
  content: string;
  status: string;
  created_at: string;
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

export default function Notifications() {
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
          renderItem={(n) => (
            <List.Item>
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
              <span style={{ color: "#999", fontSize: 12 }}>{n.created_at.replace("T", " ").slice(0, 16)}</span>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
