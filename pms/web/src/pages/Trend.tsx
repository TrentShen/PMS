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

    if (user.role === "hrbp" || user.role === "super_admin") {
      api.get<DeptTrendPoint[]>("/v1/trend/departments")
        .then((r) => setDeptPoints(r.data))
        .catch(() => setDeptPoints([]));
    }
  }, [targetId, user.role]);

  const personalChartData = useMemo(() => {
    return points
      .filter((p) => p.perf_score != null)
      .map((p) => ({
        cycle: p.cycle_name,
        score: p.perf_score,
        level: PERF_LABEL[p.perf_level ?? ""] ?? p.perf_level,
        source: p.source === "historical" ? "历史导入" : "当前系统",
      }));
  }, [points]);

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
          <Line
            data={personalChartData}
            xField="cycle"
            yField="score"
            seriesField="source"
            point={{ size: 4 }}
            smooth
            yAxis={{ min: 1, max: 5, tickInterval: 0.5 }}
            tooltip={{
              formatter: (d: { source: string; score: number; level: string }) => ({
                name: d.source,
                value: `${d.score.toFixed(2)} 分（${d.level}）`,
              }),
            }}
          />
        )}
        <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
          显示个人各周期绩效评分变化，包含当前系统已发布周期和导入的历史数据。
        </Typography.Paragraph>
      </Card>

      {deptPoints.length > 0 && (
        <Card title="部门绩效趋势">
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
          <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
            显示各部门在各周期的平均绩效评分，用于横向对比。
          </Typography.Paragraph>
        </Card>
      )}
    </Space>
  );
}
