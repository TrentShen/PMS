// 绩效趋势图（个人视角）
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, Empty, Space, Typography, message } from "antd";
import { Line } from "@ant-design/charts";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";

interface TrendPoint {
  cycle_name: string;
  perf_score: number | null;
  perf_level: string | null;
  value_belief: string | null;
  value_team: string | null;
  value_growth: string | null;
  source: "current" | "historical";
}

interface DeptTrendPoint {
  cycle_name: string;
  department_name: string;
  avg_score: number;
  participant_count: number;
}

const PERF_LABEL: Record<string, string> = {
  excellent: "优秀", exceed_part: "部分超出", meet: "符合预期", below_part: "部分不符", below: "不符合",
};
const VALUE_LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };

// 个人趋势摘要：最近一期、环比上一期、覆盖周期数
interface TrendSummary {
  latest: TrendPoint;
  latestLabel: string;
  delta: number | null; // 与上一有分周期的差值
  count: number;
}

function summarize(points: TrendPoint[]): TrendSummary | null {
  const withScore = points.filter((p) => p.perf_score != null);
  if (withScore.length === 0) return null;
  const latest = withScore[withScore.length - 1];
  const prev = withScore.length > 1 ? withScore[withScore.length - 2] : null;
  return {
    latest,
    latestLabel: PERF_LABEL[latest.perf_level ?? ""] ?? "-",
    delta: prev ? Math.round(((latest.perf_score ?? 0) - (prev.perf_score ?? 0)) * 100) / 100 : null,
    count: withScore.length,
  };
}

// 环比变化文案：上调绿、下调红、持平灰（配色类见 global.css）
function DeltaText({ delta }: { delta: number | null }) {
  if (delta === null) return <Typography.Text type="secondary">首期，无环比</Typography.Text>;
  if (delta === 0) return <Typography.Text type="secondary">环比持平</Typography.Text>;
  const up = delta > 0;
  return (
    <span className={up ? "pms-score-change-up" : "pms-score-change-down"}>
      环比 {up ? "+" : ""}{delta.toFixed(2)}
    </span>
  );
}

export default function Trend() {
  const { userId } = useParams();
  const user = useAuth((s) => s.user)!;
  const targetId = userId ? Number(userId) : user.id;
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [deptPoints, setDeptPoints] = useState<DeptTrendPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get<TrendPoint[]>(`/v1/trend/users/${targetId}`)
      .then((r) => setPoints(r.data))
      .catch((e) => message.error(formatError(e, "加载趋势失败")))
      .finally(() => setLoading(false));

    if (user.role === "hrbp" || user.role === "super_admin" || user.has_hr_permission) {
      api.get<DeptTrendPoint[]>("/v1/trend/departments")
        .then((r) => setDeptPoints(r.data))
        .catch((e) => {
          setDeptPoints([]);
          message.error(formatError(e, "加载部门趋势失败"));
        });
    }
  }, [targetId, user.role, user.has_hr_permission]);

  const personalChartData = useMemo(() => {
    return points
      .filter((p) => p.perf_score != null)
      .map((p) => ({
        cycle: p.cycle_name,
        score: p.perf_score,
        level: PERF_LABEL[p.perf_level ?? ""] ?? p.perf_level,
        source: p.source === "historical" ? "历史导入" : "当前系统",
        // 价值观三维（甲/乙/丙），tooltip 展示
        values: [p.value_belief, p.value_team, p.value_growth]
          .map((g) => VALUE_LABEL[g ?? ""])
          .filter(Boolean)
          .join("/"),
      }));
  }, [points]);

  const summary = useMemo(() => summarize(points), [points]);

  const deptChartData = useMemo(() => {
    return deptPoints.map((p) => ({
      cycle: p.cycle_name,
      score: p.avg_score,
      department: p.department_name,
      count: p.participant_count,
    }));
  }, [deptPoints]);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="个人绩效趋势" loading={loading}>
        {personalChartData.length === 0 ? (
          <Empty description="暂无趋势数据" />
        ) : (
          <>
            {/* 摘要：最近一期得分/等级 + 环比 + 覆盖周期数 */}
            {summary && (
              <Space size="middle" wrap style={{ marginBottom: 12 }}>
                <Typography.Text strong style={{ fontSize: 16 }}>
                  最近一期：{summary.latest.perf_score?.toFixed(2)} 分（{summary.latestLabel}）
                </Typography.Text>
                <DeltaText delta={summary.delta} />
                <Typography.Text type="secondary">共 {summary.count} 个周期</Typography.Text>
              </Space>
            )}
            <div
              role="img"
              aria-label={`个人绩效趋势折线图，共 ${points.length} 个周期`}
            >
              <Line
                data={personalChartData}
                xField="cycle"
                yField="score"
                seriesField="source"
                point={{ size: 4 }}
                smooth
                yAxis={{ min: 1, max: 5, tickInterval: 0.5 }}
                tooltip={{
                  formatter: (d: { source: string; score: number; level: string; values: string }) => ({
                    name: d.source,
                    value: `${d.score.toFixed(2)} 分（${d.level}）${d.values ? ` · 价值观 ${d.values}` : ""}`,
                  }),
                }}
              />
            </div>
          </>
        )}
        <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
          显示个人各周期绩效评分变化，包含当前系统已发布周期和导入的历史数据。
        </Typography.Paragraph>
      </Card>

      {deptPoints.length > 0 && (
        <Card title="部门绩效趋势">
          <div
            role="img"
            aria-label={`部门绩效趋势折线图，共 ${deptPoints.length} 个周期`}
          >
            <Line
              data={deptChartData}
              xField="cycle"
              yField="score"
              seriesField="department"
              point={{ size: 4 }}
              smooth
              yAxis={{ min: 1, max: 5, tickInterval: 0.5 }}
              tooltip={{
                formatter: (d: { department: string; score: number; count: number }) => ({
                  name: d.department,
                  value: `${d.score.toFixed(2)} 分（${d.count} 人）`,
                }),
              }}
            />
          </div>
          <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
            显示各部门在各周期的平均绩效评分，用于横向对比。
          </Typography.Paragraph>
        </Card>
      )}
    </Space>
  );
}
