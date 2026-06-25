// Leader 端：选周期 -> 列下属 -> 进入单人评估页
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, List, Select, Space, Tag } from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

interface Cycle {
  id: number;
  name: string;
  status: string;
}

interface Participant {
  id: number;
  cycle_id: number;
  user_id: number;
  user_name: string;
  user_position: string | null;
  status: string;
}

const PSTATUS_LABEL: Record<string, string> = {
  pending: "未开始自评",
  self_done: "等待上级评估",
  leader_done: "已完成上级评估",
  published: "已公布",
  excluded: "已排除",
};
const PSTATUS_COLOR: Record<string, string> = {
  pending: "default",
  self_done: "orange",
  leader_done: "blue",
  published: "green",
  excluded: "gray",
};

export default function LeaderEval() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycle, setSelectedCycle] = useState<number | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const navigate = useNavigate();
  const me = useAuth((s) => s.user)!;

  useEffect(() => {
    api.get<Cycle[]>("/v1/cycles").then((r) => {
      setCycles(r.data);
      // 默认选第一个进行中的
      const inp = r.data.find((c) => c.status === "in_progress");
      if (inp) setSelectedCycle(inp.id);
    });
  }, []);

  useEffect(() => {
    if (!selectedCycle) return;
    // 只拉自己的直属下属（不是全部参与人）
    api
      .get<{items: Participant[]; total: number}>(`/v1/cycles/${selectedCycle}/participants`, {
        params: { only_subordinates: true, page_size: 9999 },
      })
      .then((r) => setParticipants(r.data.items));
  }, [selectedCycle]);

  return (
    <Card
      title="下属评估"
      extra={
        <Select
          style={{ width: 320 }}
          placeholder="选择周期"
          value={selectedCycle ?? undefined}
          onChange={(v) => setSelectedCycle(v)}
          options={cycles.map((c) => ({
            value: c.id,
            label: `${c.name}（${c.status}）`,
          }))}
        />
      }
    >
      {participants.filter((p) => p.user_id !== me.id).length === 0 ? (
        <Empty description="没有可评估的下属" />
      ) : (
        <List
          dataSource={participants.filter((p) => p.user_id !== me.id)}
          renderItem={(p) => (
            <List.Item
              actions={[
                <a
                  key="eval"
                  onClick={() =>
                    navigate(`/leader/${p.cycle_id}/users/${p.user_id}`)
                  }
                >
                  {p.status === "pending" ? "等待自评" : p.status === "self_done" ? "去评估" : "查看"}
                </a>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    {p.user_name}
                    <Tag color={PSTATUS_COLOR[p.status]}>
                      {PSTATUS_LABEL[p.status]}
                    </Tag>
                  </Space>
                }
                description={p.user_position}
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
