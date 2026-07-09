// 价值观三维度评分表单组件（信念/团队/成长）
// 复用于自评、互评、上级评估表单
import { Form, Input, Select, Typography } from "antd";

const DIMS = [
  { key: "belief", label: "信念", desc: "创新、专业" },
  { key: "team", label: "团队", desc: "信任、坦诚" },
  { key: "growth", label: "成长", desc: "挑战、担当" },
];

const GRADE_OPTIONS = [
  { value: "jia", label: "甲 — 持续超越期望" },
  { value: "yi", label: "乙 — 基本符合价值观要求" },
  { value: "bing", label: "丙 — 不符合基本要求" },
];

interface Props {
  disabled?: boolean;
  // 前缀：适配 Form.Item name，如 prefix="value" → name="value_belief_grade"
  prefix?: string;
}

export default function ValueGradeForm({ disabled = false, prefix = "value" }: Props) {
  return (
    <>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
        请对三个价值观维度分别评级（评"甲"时必须填写具体事例）
      </Typography.Text>
      {DIMS.map((dim) => (
        <div key={dim.key} style={{ marginBottom: 16, padding: "12px 16px", background: "#fafafa", borderRadius: 8 }}>
          <Typography.Text strong>{dim.label}</Typography.Text>
          <Typography.Text type="secondary" style={{ marginLeft: 8 }}>{dim.desc}</Typography.Text>
          <div style={{ marginTop: 8 }}>
            <Form.Item
              name={`${prefix}_${dim.key}_grade`}
              label="等级"
              rules={[{ required: true, message: `请选择「${dim.label}」等级` }]}
              style={{ marginBottom: 8 }}
            >
              <Select options={GRADE_OPTIONS} disabled={disabled} placeholder="选择等级" />
            </Form.Item>
            <Form.Item
              name={`${prefix}_${dim.key}_example`}
              label="具体事例（甲时必填）"
              style={{ marginBottom: 0 }}
            >
              <Input.TextArea rows={2} disabled={disabled} placeholder={`评甲时描述「${dim.label}」方面的典范行为…`} />
            </Form.Item>
          </div>
        </div>
      ))}
    </>
  );
}

// 只读展示版本（用于结果页）
export function ValueGradeDisplay({ data, prefix = "final_value" }: { data: unknown; prefix?: string }) {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };
  return (
    <div>
      {DIMS.map((dim) => {
        const grade = record[`${prefix}_${dim.key}`] || record[`${prefix}_${dim.key}_grade`];
        if (!grade) return null;
        const gradeStr = String(grade);
        return (
          <div key={dim.key} style={{ marginBottom: 4 }}>
            <Typography.Text strong>{dim.label}：</Typography.Text>
            <Typography.Text>{LABEL[gradeStr] ?? gradeStr}</Typography.Text>
          </div>
        );
      })}
    </div>
  );
}
