// HR 管理台：周期管理 + 参与人 + Excel 导入/导出 + 催办 + 考核对象过滤
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

interface Cycle { id: number; name: string; status: string; start_date: string; end_date: string; published_at: string | null }
interface UserBrief { id: number; name: string; role: string; position: string | null }
interface Participant { id: number; cycle_id: number; user_id: number; user_name: string; user_position: string | null; status: string; final_perf_level: string | null; final_perf_score: number | null; final_value_grade: string | null }

const STATUS_LABEL: Record<string, string> = { draft: "草稿", in_progress: "进行中", published: "已公布", closed: "已归档" };

export default function HrConsole() {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user)!;
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();
  const [selectedCycle, setSelectedCycle] = useState<Cycle | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [addingIds, setAddingIds] = useState<number[]>([]);
  const [urgeOpen, setUrgeOpen] = useState(false);
  const [urgeIds, setUrgeIds] = useState<number[]>([]);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filterForm] = Form.useForm();

  async function loadCycles() { const r = await api.get<Cycle[]>("/v1/cycles"); setCycles(r.data); }
  async function loadUsers() { const r = await api.get<UserBrief[]>("/v1/users"); setUsers(r.data); }
  async function loadParticipants(cid: number) { const r = await api.get<Participant[]>(`/v1/cycles/${cid}/participants`); setParticipants(r.data); }
  useEffect(() => { loadCycles(); loadUsers(); }, []);
  useEffect(() => { if (selectedCycle) loadParticipants(selectedCycle.id); }, [selectedCycle]);

  async function onCreate(values: any) {
    try {
      await api.post("/v1/cycles", { name: values.name, start_date: values.range[0].format("YYYY-MM-DD"), end_date: values.range[1].format("YYYY-MM-DD") });
      message.success("周期已创建"); setCreateOpen(false); form.resetFields(); loadCycles();
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "创建失败"); }
  }
  async function onAddParticipants() {
    if (!selectedCycle || addingIds.length === 0) return;
    try {
      await api.post(`/v1/cycles/${selectedCycle.id}/participants`, { user_ids: addingIds });
      message.success(`已添加 ${addingIds.length} 位`); setAddingIds([]); await loadParticipants(selectedCycle.id);
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "添加失败"); }
  }
  async function onStart(c: Cycle) {
    try { await api.post(`/v1/cycles/${c.id}/start`); message.success("周期已启动"); loadCycles(); if (selectedCycle?.id === c.id) loadParticipants(c.id); }
    catch (e: any) { message.error(e?.response?.data?.detail ?? "启动失败"); }
  }
  async function onPublish(c: Cycle) {
    try { await api.post(`/v1/cycles/${c.id}/publish`); message.success("已发布"); loadCycles(); if (selectedCycle?.id === c.id) loadParticipants(c.id); }
    catch (e: any) { message.error(e?.response?.data?.detail ?? "发布失败"); }
  }

  // === Excel 导入 ===
  async function onUploadExcel(file: File) {
    if (!selectedCycle) return false;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post(`/v1/excel/import/${selectedCycle.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      message.success(`导入成功：${r.data.imported_rows} 行，${r.data.affected_users} 位员工`);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (typeof detail === "object" && detail.errors) {
        Modal.error({ title: "导入校验失败", content: detail.errors.join("\n"), width: 600 });
      } else { message.error(detail ?? "导入失败"); }
    }
    return false; // 阻止 antd 默认上传
  }

  // === Excel 导出 ===
  async function onExport() {
    if (!selectedCycle) return;
    try {
      const r = await api.get(`/v1/export/cycles/${selectedCycle.id}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `${selectedCycle.name}_绩效结果.xlsx`; a.click();
      message.success("导出成功");
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "导出失败"); }
  }

  // === 催办 ===
  async function onUrge() {
    if (!selectedCycle || urgeIds.length === 0) return;
    try {
      const r = await api.post("/v1/notify/urge", { cycle_id: selectedCycle.id, user_ids: urgeIds });
      message.success(`已催办 ${r.data.sent} 人`); setUrgeOpen(false); setUrgeIds([]);
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "催办失败"); }
  }

  // === 考核对象过滤 ===
  async function onFilter(values: any) {
    if (!selectedCycle) return;
    try {
      const r = await api.post(`/v1/cycles/${selectedCycle.id}/suggest-participants`, {
        exclude_roles: values.exclude_roles || [],
        min_hired_before: values.min_hired_before?.format("YYYY-MM-DD") || null,
      });
      const ids = r.data.map((u: any) => u.id);
      if (ids.length === 0) { message.warning("按条件未筛选到人"); return; }
      await api.post(`/v1/cycles/${selectedCycle.id}/participants`, { user_ids: ids });
      message.success(`已按条件添加 ${ids.length} 人`);
      setFilterOpen(false); filterForm.resetFields();
      await loadParticipants(selectedCycle.id);
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "操作失败"); }
  }

  const availableUsers = users.filter((u) => u.role !== "super_admin" && u.role !== "hrbp" && !participants.find((p) => p.user_id === u.id));
  const pendingParticipants = participants.filter((p) => p.status === "pending" || p.status === "self_done");

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 周期列表 */}
      <Card title="周期管理" extra={<Button type="primary" onClick={() => setCreateOpen(true)}>新建周期</Button>}>
        <List
          dataSource={cycles}
          renderItem={(c) => (
            <List.Item actions={[
              <a key="sel" onClick={() => setSelectedCycle(c)}>详情</a>,
              c.status === "draft" && <Popconfirm key="start" title="启动后不能再加人，确认？" onConfirm={() => onStart(c)}><a>启动</a></Popconfirm>,
              c.status === "in_progress" && <Popconfirm key="pub" title="需要先完成校准审批，确认发布？" onConfirm={() => onPublish(c)}><a style={{ color: "#f59e0b" }}>发布</a></Popconfirm>,
            ].filter(Boolean) as any}>
              <List.Item.Meta
                title={<Space>{c.name} <Tag color="blue">{STATUS_LABEL[c.status]}</Tag></Space>}
                description={`${c.start_date} ~ ${c.end_date}`}
              />
            </List.Item>
          )}
        />
      </Card>

      {/* 参与人详情 */}
      {selectedCycle && (
        <Card
          title={`参与人（${selectedCycle.name}）`}
          extra={
            <Space>
              <Tag color="blue">{STATUS_LABEL[selectedCycle.status]}</Tag>
              {/* Excel 操作 */}
              <Button size="small" icon={<DownloadOutlined />} href="/api/v1/excel/template">下载导入模板</Button>
              <Upload accept=".xlsx" showUploadList={false} beforeUpload={(f) => onUploadExcel(f)}>
                <Button size="small" icon={<UploadOutlined />}>Excel 导入目标</Button>
              </Upload>
              {selectedCycle.status === "published" && (
                <Button size="small" icon={<DownloadOutlined />} onClick={onExport}>导出结果</Button>
              )}
              {/* 催办 */}
              {selectedCycle.status === "in_progress" && (
                <Button size="small" onClick={() => { setUrgeIds(pendingParticipants.map((p) => p.user_id)); setUrgeOpen(true); }}>催办</Button>
              )}
            </Space>
          }
        >
          {/* 草稿：加参与人 */}
          {selectedCycle.status === "draft" && (
            <Space style={{ marginBottom: 16 }} wrap>
              <Select mode="multiple" placeholder="选择员工" style={{ minWidth: 360 }} value={addingIds} onChange={setAddingIds}
                options={availableUsers.map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }))} />
              <Button type="primary" onClick={onAddParticipants}>添加</Button>
              <Button onClick={() => setFilterOpen(true)}>按条件筛选添加</Button>
            </Space>
          )}
          {selectedCycle.status === "draft" && participants.length === 0 && (
            <Alert type="info" message="尚未添加参与人" />
          )}
          <Table rowKey="id" size="small" dataSource={participants} pagination={false} columns={[
            { title: "姓名", dataIndex: "user_name" },
            { title: "职位", dataIndex: "user_position" },
            { title: "进度", dataIndex: "status", render: (s) => <Tag>{s}</Tag> },
            { title: "业绩", render: (_, r) => r.final_perf_score != null ? `${r.final_perf_score.toFixed(2)}` : "-" },
            { title: "价值观", dataIndex: "final_value_grade", render: (v) => v ?? "-" },
            {
              title: "操作",
              render: (_, r) => (
                <Space>
                  {selectedCycle.status === "published" && (
                    <a onClick={() => navigate(`/feedback/${selectedCycle.id}/${r.user_id}`)}>写反馈</a>
                  )}
                </Space>
              ),
            },
          ]} />
        </Card>
      )}

      {/* 新建周期弹窗 */}
      <Modal title="新建周期" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={onCreate}>
          <Form.Item name="name" label="周期名" initialValue="2025 下半年度绩效考核" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="range" label="考核周期" initialValue={[dayjs("2025-07-01"), dayjs("2025-12-31")]} rules={[{ required: true }]}><DatePicker.RangePicker /></Form.Item>
        </Form>
      </Modal>

      {/* 催办弹窗 */}
      <Modal title="催办未完成人员" open={urgeOpen} onCancel={() => setUrgeOpen(false)} onOk={onUrge}>
        <Typography.Paragraph>将向以下 {urgeIds.length} 人发送催办通知：</Typography.Paragraph>
        <Select mode="multiple" style={{ width: "100%" }} value={urgeIds} onChange={setUrgeIds}
          options={participants.map((p) => ({ value: p.user_id, label: `${p.user_name}（${p.status}）` }))} />
      </Modal>

      {/* 时间线配置 */}
      {selectedCycle && (
        <StageConfigPanel cycleId={selectedCycle.id} cycleStatus={selectedCycle.status} />
      )}

      {/* 按条件筛选参与人弹窗 */}
      <Modal title="按条件筛选参与人" open={filterOpen} onCancel={() => setFilterOpen(false)} onOk={() => filterForm.submit()}>
        <Form form={filterForm} layout="vertical" onFinish={onFilter}>
          <Form.Item name="exclude_roles" label="排除角色">
            <Select mode="multiple" options={[
              { value: "super_admin", label: "超级管理员" },
              { value: "hrbp", label: "HR" },
              { value: "dept_leader", label: "部门 Leader" },
            ]} />
          </Form.Item>
          <Form.Item name="min_hired_before" label="入职日期不晚于" extra="只纳入在此日期前入职的员工">
            <DatePicker />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

// ========== 时间线配置面板（PRD 3.2.3）==========
function StageConfigPanel({ cycleId, cycleStatus }: { cycleId: number; cycleStatus: string }) {
  const [stageForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get(`/v1/notify/cycles/${cycleId}/stages`).then((r) => {
      if (r.data.stages) {
        // 把 "2025-01-06" 字符串转成 dayjs
        const vals: any = {};
        for (const [k, v] of Object.entries(r.data.stages)) {
          vals[k] = v ? dayjs(v as string) : null;
        }
        stageForm.setFieldsValue(vals);
      }
    });
  }, [cycleId]);

  async function onSave() {
    const vals = await stageForm.validateFields();
    // 把 dayjs 转成 "YYYY-MM-DD" 字符串
    const payload: any = {};
    for (const [k, v] of Object.entries(vals)) {
      if (v) payload[k] = (v as any).format("YYYY-MM-DD");
    }
    setLoading(true);
    try {
      await api.put(`/v1/notify/cycles/${cycleId}/stages`, payload);
      message.success("时间线已保存");
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "保存失败");
    } finally { setLoading(false); }
  }

  const STAGES = [
    { key: "self_eval", label: "自评" },
    { key: "peer_confirm", label: "互评名单确认" },
    { key: "peer_eval", label: "互评" },
    { key: "superior_eval", label: "上级评估" },
    { key: "calibration", label: "绩效校准" },
    { key: "approval", label: "公司级审批" },
    { key: "feedback", label: "绩效反馈" },
  ];

  return (
    <Card title="时间线配置（各环节截止日期）" extra={
      <Button type="primary" size="small" onClick={onSave} loading={loading}>保存时间线</Button>
    }>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="配置后系统会在截止前3天、1天和当天自动发送提醒（企微消息接入后自动推送）" />
      <Form form={stageForm} layout="inline" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {STAGES.map((s) => (
          <Space key={s.key} style={{ display: "flex", alignItems: "center" }}>
            <span style={{ width: 100 }}>{s.label}：</span>
            <Form.Item name={`${s.key}_start`} noStyle><DatePicker placeholder="开始" size="small" /></Form.Item>
            <span>~</span>
            <Form.Item name={`${s.key}_end`} noStyle><DatePicker placeholder="截止" size="small" /></Form.Item>
          </Space>
        ))}
        <Space style={{ display: "flex", alignItems: "center" }}>
          <span style={{ width: 100 }}>结果公布：</span>
          <Form.Item name="publish_date" noStyle><DatePicker placeholder="公布日" size="small" /></Form.Item>
        </Space>
      </Form>
    </Card>
  );
}
