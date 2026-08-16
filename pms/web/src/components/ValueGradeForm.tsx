// 价值观评分表单组件（界面合并为单项，提交时由 expandValueGrades 展开为后端三维度字段）
// 复用于自评、互评、上级评估、校准表单
import { Form, Input, Radio, Typography } from "antd";

// 按钮直选，label 保持简短避免移动端溢出；等级含义在下方说明
const GRADE_OPTIONS = [
  { value: "jia", label: "甲" },
  { value: "yi", label: "乙" },
  { value: "bing", label: "丙" },
];

const GRADE_LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };

interface Props {
  disabled?: boolean;
  // 前缀：适配 Form.Item name，如 prefix="value" → name="value_belief_grade"
  // 界面只采集 belief 一组字段，提交时展开复制到 team/growth，各表单 Form 结构不变
  prefix?: string;
}

export default function ValueGradeForm({ disabled = false, prefix = "value" }: Props) {
  return (
    <>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
        甲=持续超越期望，乙=基本符合价值观要求，丙=不符合基本要求（评"甲"时必须填写具体事例）
      </Typography.Text>
      <div style={{ marginBottom: 16, padding: "var(--space-3) var(--space-4)", background: "var(--color-surface-raised)", borderRadius: "var(--radius-lg)" }}>
        <Form.Item
          name={`${prefix}_belief_grade`}
          label="价值观评分"
          rules={[{ required: true, message: "请选择价值观等级" }]}
          style={{ marginBottom: 8 }}
        >
          <Radio.Group
            options={GRADE_OPTIONS}
            optionType="button"
            buttonStyle="solid"
            size="large"
            disabled={disabled}
          />
        </Form.Item>
        <Form.Item
          name={`${prefix}_belief_example`}
          label="事例（选甲时必填）"
          dependencies={[`${prefix}_belief_grade`]}
          rules={[
            ({ getFieldValue }) => ({
              validator(_, value: string | undefined) {
                if (getFieldValue(`${prefix}_belief_grade`) === "jia" && (!value || !value.trim())) {
                  return Promise.reject(new Error("选择甲等评价时，请填写具体事例"));
                }
                return Promise.resolve();
              },
            }),
          ]}
          style={{ marginBottom: 0 }}
          extra="从信念、团队协作、学习成长三方面综合评价"
        >
          <Input.TextArea rows={2} disabled={disabled} placeholder="评甲时描述价值观方面的典范行为…" />
        </Form.Item>
      </div>
    </>
  );
}

// 提交时把单项价值观评分展开为后端三维度字段（grade/example 同步复制，
// 保证后端 validate_value_grades 的"甲必须填事例"校验三维一致通过）
export function expandValueGrades<T extends { value_belief_grade?: string | null; value_belief_example?: string | null }>(
  values: T
): T & {
  value_team_grade: string | null;
  value_team_example: string | null;
  value_growth_grade: string | null;
  value_growth_example: string | null;
} {
  return {
    ...values,
    value_team_grade: values.value_belief_grade ?? null,
    value_team_example: values.value_belief_example ?? null,
    value_growth_grade: values.value_belief_grade ?? null,
    value_growth_example: values.value_belief_example ?? null,
  };
}

// 只读展示版本（用于结果页）：三维合并为单个"价值观"，
// 兼容老数据：belief 为空时依次回退 team/growth
export function ValueGradeDisplay({ data, prefix = "final_value" }: { data: unknown; prefix?: string }) {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const pick = (dim: string) => record[`${prefix}_${dim}`] || record[`${prefix}_${dim}_grade`];
  const grade = pick("belief") ?? pick("team") ?? pick("growth");
  if (!grade) return null;
  const gradeStr = String(grade);
  return (
    <div>
      <Typography.Text strong>价值观：</Typography.Text>
      <Typography.Text>{GRADE_LABEL[gradeStr] ?? gradeStr}</Typography.Text>
    </div>
  );
}
