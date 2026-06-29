// HR 绩效看板：展示某个绩效周期各环节整体进度
import { useEffect, useState } from "react";
import { Card, Col, Progress, Row, Select, Space, Statistic, Typography, message } from "antd";
import { api } from "@/services/api";

interface CycleBrief {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  objective_cycle_id: number | null;
}

interface DashboardData {
  cycle: CycleBrief;
  objective_cycle_participant_count: number;
  performance_participant_count: number;
  self_eval_done: number;
  self_eval_total: number;
  peer_list_confirmed: number;
  peer_eval_done: number;
  superior_eval_done: number;
  superior_eval_total: number;
  self_eval_progress_by_department: {
    department_id: number;
    department_name: string;
    total: number;
    done: number;
    undone: number;
  }[];
  peer_eval_progress_by_department: {
    department_id: number;
    department_name: string;
    total: number;
    done: number;
    undone: number;
  }[];
}

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  in_progress: "进行中",
  published: "已公布",
  closed: "已归档",
};

export default function HrDashboard() {
  const [cycles, setCycles] = useState<CycleBrief[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    api.get<CycleBrief[]>("/v1/cycles").then((r) => {
      setCycles(r.data);
      if (r.data.length > 0 && !selectedCycleId) {
        setSelectedCycleId(r.data[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedCycleId) return;
    api.get<DashboardData>(`/v1/cycles/${selectedCycleId}/dashboard`)
      .then((r) => setData(r.data))
      .catch((e: any) => message.error(e?.response?.data?.detail ?? "加载失败"));
  }, [selectedCycleId]);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="绩效看板">
        <Select
          style={{ width: 320 }}
          placeholder="选择绩效周期"
          value={selectedCycleId}
          onChange={(v) => setSelectedCycleId(v)}
          options={cycles.map((c) => ({ value: c.id, label: `${c.name}（${STATUS_LABEL[c.status]}）` }))}
        />
      </Card>

      {data && (
        <>
          <Card title={data.cycle.name}>
            <DescriptionsRow data={data} />
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title="自评完成进度 - 部门">
                <DepartmentProgress data={data.self_eval_progress_by_department} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="互评完成进度 - 部门">
                <DepartmentProgress data={data.peer_eval_progress_by_department} />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Space>
  );
}

function DescriptionsRow({ data }: { data: DashboardData }) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={12} md={8} lg={4}>
        <Statistic
          title="参与绩效目标设定人数"
          value={data.objective_cycle_participant_count}
          suffix="人"
        />
      </Col>
      <Col xs={12} md={8} lg={4}>
        <Statistic
          title="参与绩效评估人数"
          value={data.performance_participant_count}
          suffix="人"
        />
      </Col>
      <Col xs={12} md={8} lg={4}>
        <Statistic
          title="自评完成"
          value={data.self_eval_done}
          suffix={`/ ${data.self_eval_total}`}
          valueStyle={{ color: data.self_eval_done === data.self_eval_total ? "#52c41a" : "#1677ff" }}
        />
      </Col>
      <Col xs={12} md={8} lg={4}>
        <Statistic title="互评名单确认" value={data.peer_list_confirmed} suffix="人" />
      </Col>
      <Col xs={12} md={8} lg={4}>
        <Statistic title="互评完成" value={data.peer_eval_done} suffix="人" />
      </Col>
      <Col xs={12} md={8} lg={4}>
        <Statistic
          title="上级评估完成"
          value={data.superior_eval_done}
          suffix={`/ ${data.superior_eval_total}`}
          valueStyle={{ color: data.superior_eval_done === data.superior_eval_total ? "#52c41a" : "#1677ff" }}
        />
      </Col>
    </Row>
  );
}

function DepartmentProgress({
  data,
}: {
  data: { department_id: number; department_name: string; total: number; done: number; undone: number }[];
}) {
  if (data.length === 0) {
    return <Typography.Text type="secondary">暂无数据</Typography.Text>;
  }

  // 按总数倒序，便于看重点部门
  const sorted = [...data].sort((a, b) => b.total - a.total);

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {sorted.map((d) => {
        const percent = d.total === 0 ? 0 : Math.round((d.done / d.total) * 100);
        return (
          <div key={d.department_id}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span>{d.department_name}</span>
              <span>
                {d.done} / {d.total}（{percent}%）
              </span>
            </div>
            <Progress percent={percent} size="small" status={percent === 100 ? "success" : "active"} />
          </div>
        );
      })}
    </Space>
  );
}
