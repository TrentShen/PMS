// 历史绩效查询（PRD 3.6.1 个人视角）
// 员工看到自己所有已发布周期的结果；Leader/HR 可切员工看下属
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, Select, Space, Table, Tag, Typography } from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { ROLE } from "@/App";

interface MyCycleItem {
  cycle: { id: number; name: string; status: string; start_date: string; end_date: string };
  participant_status: string;
  final_perf_score: number | null;
  final_perf_level: string | null;
  final_value_belief: string | null;
  final_value_team: string | null;
  final_value_growth: string | null;
}

const PERF_LABEL: Record<string, string> = {
  excellent: "优秀", exceed_part: "部分超出", meet: "符合预期", below_part: "部分不符", below: "不符合",
};
const VALUE_LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };
const PERF_COLOR: Record<string, string> = {
  excellent: "gold", exceed_part: "blue", meet: "green", below_part: "orange", below: "red",
};

export default function History() {
  const user = useAuth((s) => s.user)!;
  const navigate = useNavigate();
  const [cycles, setCycles] = useState<MyCycleItem[]>([]);

  useEffect(() => {
    api.get<MyCycleItem[]>("/v1/cycles/mine").then((r) => {
      // 只展示已发布的
      setCycles(r.data.filter((c) => c.cycle.status === "published"));
    });
  }, []);

  const published = cycles.filter((c) => c.participant_status === "published");

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="我的历史绩效">
        {published.length === 0 ? (
          <Empty description="暂无已公布的绩效结果" />
        ) : (
          <Table
            rowKey={(r) => r.cycle.id}
            dataSource={published}
            pagination={false}
            columns={[
              { title: "周期", dataIndex: ["cycle", "name"] },
              { title: "考核期间", render: (_, r) => `${r.cycle.start_date} ~ ${r.cycle.end_date}` },
              {
                title: "业绩",
                render: (_, r) => r.final_perf_score != null ? (
                  <Space>
                    <Tag color={PERF_COLOR[r.final_perf_level ?? ""]}>
                      {PERF_LABEL[r.final_perf_level ?? ""] ?? "-"}
                    </Tag>
                    <Typography.Text>{r.final_perf_score.toFixed(2)} 分</Typography.Text>
                  </Space>
                ) : "-",
              },
              {
                title: "价值观",
                render: (_, r) => (
                  <Space>
                    <Tag>信念 {VALUE_LABEL[r.final_value_belief ?? ""] ?? "-"}</Tag>
                    <Tag>团队 {VALUE_LABEL[r.final_value_team ?? ""] ?? "-"}</Tag>
                    <Tag>成长 {VALUE_LABEL[r.final_value_growth ?? ""] ?? "-"}</Tag>
                  </Space>
                ),
              },
              {
                title: "操作",
                render: (_, r) => (
                  <Space>
                    <a onClick={() => navigate(`/self/${r.cycle.id}`)}>查看详情</a>
                    <a onClick={() => navigate(`/feedback/${r.cycle.id}`)}>查看反馈</a>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>
    </Space>
  );
}
