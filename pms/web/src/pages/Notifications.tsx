// 通知中心页面（PRD 3.5）
import { useEffect, useState } from "react";
import { Card, Empty, List, Tag } from "antd";
import { api } from "@/services/api";

interface Notify {
  id: number;
  title: string;
  content: string;
  status: string;
  created_at: string;
}

const STATUS_COLOR: Record<string, string> = { pending: "orange", sent: "green", failed: "red" };

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
                title={<>{n.title} <Tag color={STATUS_COLOR[n.status]}>{n.status}</Tag></>}
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
