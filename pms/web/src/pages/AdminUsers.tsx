// 超管专属：用户与权限管理
// 支持编辑：角色 / 直属上级 / 部门 / HR 管辖范围 / 账号状态
import { useEffect, useState } from "react";
import {
  Alert,
  Card,
  Form,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tooltip,
  Typography,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";


interface AdminUser {
  id: number;
  wecom_userid: string;
  name: string;
  role: string;
  position: string | null;
  leader_userid: string | null;
  department_id: number | null;
  hrbp_scope_dept_ids: number[] | null;
  status: string;
  // 后端标记：角色含 Leader 但无任何下属（可选字段，后端未上线时缺失则不渲染提示）
  role_mismatch?: boolean;
}

interface Dept {
  id: number;
  name: string;
  parent_id: number | null;
}

const ROLE_OPTIONS = [
  { value: "super_admin", label: "超级管理员" },
  { value: "hrbp", label: "HR" },
  { value: "dept_leader", label: "部门 Leader" },
  { value: "direct_leader", label: "直属上级" },
  { value: "employee", label: "员工" },
];
const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((o) => [o.value, o.label])
);

function buildDeptPath(deptId: number | null, depts: Dept[]): string {
  if (!deptId) return "";
  const map = new Map(depts.map((d) => [d.id, d]));
  const parts: string[] = [];
  let current = map.get(deptId);
  while (current) {
    parts.unshift(current.name);
    current = current.parent_id ? map.get(current.parent_id) : undefined;
  }
  return parts.join(" / ");
}

const ROLE_STATUS_TYPE: Record<string, StatusType> = {
  super_admin: "danger",
  hrbp: "warning",
  dept_leader: "primary",
  direct_leader: "info",
  employee: "success",
};

const USER_STATUS_LABEL: Record<string, string> = { active: "在职", inactive: "离职" };

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [depts, setDepts] = useState<Dept[]>([]);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [u, d] = await Promise.all([
        api.get<AdminUser[]>("/v1/admin/users"),
        api.get<Dept[]>("/v1/admin/departments"),
      ]);
      setUsers(u.data);
      setDepts(d.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch((e) => message.error(formatError(e, "加载失败")));
  }, []);

  function openEdit(u: AdminUser) {
    setEditing(u);
    form.setFieldsValue({
      role: u.role,
      leader_userid: u.leader_userid ?? "",
      department_id: u.department_id ?? 0,
      // 把"null=全局"转成 UI 可操作的开关
      scope_global: u.hrbp_scope_dept_ids === null,
      hrbp_scope_dept_ids: u.hrbp_scope_dept_ids ?? [],
      status: u.status,
    });
  }

  async function onSave() {
    if (!editing) return;
    setSaving(true);
    try {
      const values = await form.validateFields();
      const payload: Record<string, unknown> = {
        role: values.role,
        // Select allowClear 后值为 undefined 会被 JSON 序列化丢弃，后端语义是"不修改"；清空需显式传空串
        leader_userid: values.leader_userid ?? "",
        // 后端约定 department_id == 0 表示清空部门，None 表示不修改，原样透传保留 0
        department_id: values.department_id,
        status: values.status,
      };
      // 仅当被编辑用户是 HR 时，处理管辖范围字段
      if (values.role === "hrbp") {
        if (values.scope_global) {
          payload.clear_scope = true;
        } else {
          payload.hrbp_scope_dept_ids = values.hrbp_scope_dept_ids ?? [];
        }
      } else {
        // 非 HR 不需要管辖范围；为避免遗留值影响，改为 null
        payload.clear_scope = true;
      }
      await api.patch(`/v1/admin/users/${editing.id}`, payload);
      message.success("已保存");
      setEditing(null);
      await load();
    } catch (e) {
      // antd 校验失败 reject 出 errorFields 对象，表单已有红字提示，无需额外 message
      if ((e as { errorFields?: unknown[] })?.errorFields) return;
      message.error(formatError(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  }

  // 直属上级候选：除当前用户外所有 active 用户
  const leaderOptions = users
    .filter((u) => u.id !== editing?.id && u.status === "active")
    .map((u) => ({ value: u.wecom_userid, label: `${u.name}（${u.wecom_userid}）` }));

  return (
    <Card title="用户与权限管理">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="超级管理员专属。改完后登录的用户需切换身份重新登录才能看到新权限。"
      />

      <Table
        rowKey="id"
        dataSource={users}
        pagination={false}
        size="small"
        loading={loading}
        scroll={{ x: 1000 }}
        columns={[
          { title: "姓名", dataIndex: "name" },
          { title: "账号", dataIndex: "wecom_userid" },
          {
            title: "角色",
            dataIndex: "role",
            render: (r: string, u: AdminUser) => (
              <Space size={4}>
                <StatusTag type={ROLE_STATUS_TYPE[r] ?? "default"}>{ROLE_LABEL[r] ?? r}</StatusTag>
                {u.role_mismatch === true && (
                  <Tooltip title="担任 Leader 角色但无下属，请确认是否为历史遗留">
                    <StatusTag type="warning">角色待核查</StatusTag>
                  </Tooltip>
                )}
              </Space>
            ),
          },
          {
            title: "部门",
            dataIndex: "department_id",
            render: (id) =>
              id ? (
                buildDeptPath(id, depts) || id
              ) : (
                <Typography.Text type="secondary">-</Typography.Text>
              ),
          },
          {
            title: "直属上级",
            dataIndex: "leader_userid",
            render: (v) => v ?? <Typography.Text type="secondary">-</Typography.Text>,
          },
          {
            title: "HR 管辖范围",
            dataIndex: "hrbp_scope_dept_ids",
            render: (v: number[] | null | undefined, r: AdminUser) => {
              if (r.role !== "hrbp") return <Typography.Text type="secondary">-</Typography.Text>;
              if (v === null || v === undefined)
                return <StatusTag type="warning">全局</StatusTag>;
              if (v.length === 0)
                return <StatusTag type="danger">无</StatusTag>;
              const names = v.map((id) => depts.find((d) => d.id === id)?.name ?? id);
              return <Space>{names.map((n, i) => <StatusTag key={i}>{n}</StatusTag>)}</Space>;
            },
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (s: string) => (
              <StatusTag type={s === "active" ? "success" : "default"}>{USER_STATUS_LABEL[s] ?? s}</StatusTag>
            ),
          },
          {
            title: "操作",
            render: (_, u) => <a onClick={() => openEdit(u)}>编辑</a>,
          },
        ]}
      />

      <Modal
        open={!!editing}
        title={editing ? `编辑：${editing.name}` : ""}
        onCancel={() => setEditing(null)}
        onOk={onSave}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="department_id" label="所属部门">
            <Select
              options={[
                { value: 0, label: "（无）" },
                ...depts.map((d) => ({ value: d.id, label: d.name })),
              ]}
            />
          </Form.Item>
          <Form.Item name="leader_userid" label="直属上级（wecom_userid）">
            <Select allowClear options={leaderOptions} placeholder="留空表示无上级" />
          </Form.Item>

          {/* 管辖范围：仅角色为 HR 时显示 */}
          <Form.Item
            shouldUpdate={(a, b) => a.role !== b.role}
            noStyle
          >
            {({ getFieldValue }) =>
              getFieldValue("role") === "hrbp" ? (
                <>
                  <Form.Item
                    name="scope_global"
                    label="HR 管辖范围：全局可见"
                    valuePropName="checked"
                    extra="打开表示不限部门；关闭后选择具体部门"
                  >
                    <Switch />
                  </Form.Item>
                  <Form.Item
                    shouldUpdate={(a, b) => a.scope_global !== b.scope_global}
                    noStyle
                  >
                    {({ getFieldValue: g }) =>
                      !g("scope_global") ? (
                        <Form.Item
                          name="hrbp_scope_dept_ids"
                          label="可管辖的部门（含子部门）"
                        >
                          <Select
                            mode="multiple"
                            options={depts.map((d) => ({
                              value: d.id,
                              label: d.parent_id
                                ? `${depts.find((x) => x.id === d.parent_id)?.name}/${d.name}`
                                : d.name,
                            }))}
                          />
                        </Form.Item>
                      ) : null
                    }
                  </Form.Item>
                </>
              ) : null
            }
          </Form.Item>

          <Form.Item name="status" label="状态">
            <Select
              options={[
                { value: "active", label: "在职" },
                { value: "inactive", label: "离职（保留历史数据）" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
