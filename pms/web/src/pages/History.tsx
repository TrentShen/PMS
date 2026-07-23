// 历史绩效查询（PRD 3.6.1 个人视角）
// 员工看到自己所有已发布周期的结果；Leader/HR 可切员工看下属
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, Space, Table, Tag, Typography } from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

interface MyCycleItem {
  cycle: { id: number; name: string; status: string; start_date: string; end_date: string };
  participant_status: string;
  final_perf_score: number | null;
  final_perf_level: string | null;
  final_value_belief: string | null;
  final_value_team: string | null;
  final_value_growth: string | null;
}

interface HistoricalItem {
  id: number;
  user_id: number;
  user_name: string;
  cycle_name: string;
  perf_score: number | null;
  perf_level: string | null;
  value_belief: string | null;
  value_team: string | null;
  value_growth: string | null;
  comment: string | null;
  imported_by: string;
  created_at: string;
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
  const [historical, setHistorical] = useState<HistoricalItem[]>([]);

  useEffect(() => {
    api.get<MyCycleItem[]>("/v1/cycles/mine").then((r) => {
      // 只展示已发布的
      setCycles(r.data.filter((c) => c.cycle.status === "published"));
    });
    api.get<HistoricalItem[]>("/v1/import/historical-performance").then((r) => {
      setHistorical(r.data.filter((h) => h.user_id === user.id));
    }).catch(() => setHistorical([]));
  }, []);

  const published = cycles.filter((c) => c.participant_status === "published");

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="我的历史绩效" extra={<a onClick={() => navigate("/trend")}>查看趋势图</a>}>
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

      {historical.length > 0 && (
        <Card title="历史考核记录（只读）">
          <Table
            rowKey="id"
            dataSource={historical}
            pagination={false}
            columns={[
              { title: "周期", dataIndex: "cycle_name" },
              {
                title: "业绩",
                render: (_, r) => r.perf_score != null ? (
                  <Space>
                    <Tag color={PERF_COLOR[r.perf_level ?? ""]}>
                      {PERF_LABEL[r.perf_level ?? ""] ?? "-"}
                    </Tag>
                    <Typography.Text>{r.perf_score.toFixed(2)} 分</Typography.Text>
                  </Space>
                ) : "-",
              },
              {
                title: "价值观",
                render: (_, r) => (
                  <Space>
                    <Tag>信念 {VALUE_LABEL[r.value_belief ?? ""] ?? "-"}</Tag>
                    <Tag>团队 {VALUE_LABEL[r.value_team ?? ""] ?? "-"}</Tag>
                    <Tag>成长 {VALUE_LABEL[r.value_growth ?? ""] ?? "-"}</Tag>
                  </Space>
                ),
              },
              { title: "评语", dataIndex: "comment", render: (c) => c || "-" },
            ]}
          />
        </Card>
      )}
    </Space>
  );
}
