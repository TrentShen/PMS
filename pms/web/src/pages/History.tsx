// 历史绩效查询（PRD 3.6.1 个人视角）
// 员工看到自己所有已发布周期的结果；Leader/HR 可切员工看下属
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, message, Space, Table, Tag, Typography } from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { HistoricalObjective } from "@/services/api.types";

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
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const [cycles, setCycles] = useState<MyCycleItem[]>([]);
  const [historical, setHistorical] = useState<HistoricalItem[]>([]);
  const [histObjectives, setHistObjectives] = useState<HistoricalObjective[]>([]);

  useEffect(() => {
    api.get<MyCycleItem[]>("/v1/cycles/mine").then((r) => {
      // 只展示已发布的
      setCycles(r.data.filter((c) => c.cycle.status === "published"));
    });
    // 后端已按当前用户过滤，直接使用返回数据
    api.get<HistoricalItem[]>("/v1/import/historical-performance").then((r) => {
      setHistorical(r.data);
    }).catch(() => setHistorical([]));
    // 历史目标：当前页面只看自己（非 HR 后端也只允许查自己）
    if (user) {
      api.get<HistoricalObjective[]>("/v1/import/historical-objectives", {
        params: { user_id: user.id },
      }).then((r) => {
        setHistObjectives(r.data);
      }).catch((e) => {
        message.error(formatError(e, "历史目标加载失败"));
      });
    }
  }, [user]);

  const published = cycles.filter((c) => c.participant_status === "published");

  // 历史目标按周期分组（保持接口返回顺序，组内按 order_num 排序）
  const objectiveGroups: [string, HistoricalObjective[]][] = [];
  for (const o of histObjectives) {
    const group = objectiveGroups.find(([name]) => name === o.cycle_name);
    if (group) {
      group[1].push(o);
    } else {
      objectiveGroups.push([o.cycle_name, [o]]);
    }
  }
  for (const [, objs] of objectiveGroups) {
    objs.sort((a, b) => a.order_num - b.order_num);
  }

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
                render: (_, r) =>
                  VALUE_LABEL[r.final_value_belief ?? r.final_value_team ?? r.final_value_growth ?? ""] ?? "-",
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
                render: (_, r) =>
                  VALUE_LABEL[r.value_belief ?? r.value_team ?? r.value_growth ?? ""] ?? "-",
              },
              { title: "评语", dataIndex: "comment", render: (c) => c || "-" },
            ]}
          />
        </Card>
      )}

      {objectiveGroups.length > 0 && (
        <Card title="历史目标（只读）">
          {objectiveGroups.map(([cycleName, objs]) => (
            <div key={cycleName} style={{ marginBottom: 16 }}>
              <Typography.Title level={5} style={{ marginTop: 0 }}>{cycleName}</Typography.Title>
              {objs.map((o) => (
                <Card key={o.id} size="small" style={{ marginBottom: 8 }}>
                  <Space size={8}>
                    <Typography.Text strong>{o.title}</Typography.Text>
                    {o.weight > 0 && <Tag>权重 {o.weight}</Tag>}
                  </Space>
                  {o.description && (
                    <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 4, whiteSpace: "pre-wrap" }}>
                      {o.description}
                    </Typography.Paragraph>
                  )}
                  {o.measure_criteria && (
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                      衡量标准：{o.measure_criteria}
                    </Typography.Paragraph>
                  )}
                </Card>
              ))}
            </div>
          ))}
        </Card>
      )}
    </Space>
  );
}
