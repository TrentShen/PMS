// 目标导入结果弹窗：成功 N 人 M 条 + 跳过明细
// 试用期目标导入与历史目标导入共用同一响应结构
import { Modal, Typography } from "antd";
import type { ObjectiveImportResult } from "@/services/api.types";

export function showObjectiveImportResult(result: ObjectiveImportResult): void {
  Modal.info({
    title: `导入完成：成功 ${result.imported_users} 人，共 ${result.imported_objectives} 条目标`,
    width: 600,
    content:
      result.skipped.length > 0 ? (
        <div>
          <Typography.Text type="warning">跳过 {result.skipped.length} 条：</Typography.Text>
          <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
            {result.skipped.map((s, i) => (
              <li key={i}>
                {s.name}（{s.wecom_userid}）：{s.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null,
  });
}
