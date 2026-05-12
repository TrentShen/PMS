# HRBP 绩效结果导出（PRD 3.6.1）
# 导出已发布周期的结果为 Excel + 记 export_log
import io
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlmodel import Session, select

from pms.database.models.audit import ExportLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import require_role
from pms.services.scope import visible_user_ids

router = APIRouter(prefix="/export", tags=["export"])

# 每次最大导出行数（防止一次拉太多）
MAX_EXPORT_ROWS = 200

PERF_LABEL = {
    "excellent": "优秀", "exceed_part": "部分超出预期",
    "meet": "符合预期", "below_part": "部分不符合预期", "below": "不符合预期",
}
VALUE_LABEL = {"jia": "甲", "yi": "乙", "bing": "丙"}


@router.get("/cycles/{cycle_id}")
def export_cycle_results(
    cycle_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "published":
        raise HTTPException(status_code=400, detail="只能导出已发布的周期")

    # 按 HR 管辖范围过滤
    scope = visible_user_ids(session, hr)
    q = select(CycleParticipant, User).join(
        User, User.id == CycleParticipant.user_id
    ).where(CycleParticipant.cycle_id == cycle_id)
    if scope is not None:
        q = q.where(CycleParticipant.user_id.in_(scope))

    rows = session.exec(q).all()
    if len(rows) > MAX_EXPORT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"导出行数 {len(rows)} 超过上限 {MAX_EXPORT_ROWS}，请缩小范围",
        )

    # 生成 Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "绩效结果"
    ws.append([
        "姓名", "员工ID", "部门", "职位",
        "业绩分", "业绩等级", "价值观等级",
    ])
    for p, u in rows:
        ws.append([
            u.name,
            u.wecom_userid,
            p.dept_name_snapshot,
            u.position,
            p.final_perf_score,
            PERF_LABEL.get(p.final_perf_level or "", ""),
            VALUE_LABEL.get(p.final_value_grade or "", ""),
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    file_name = f"{cycle.name}_绩效结果_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"

    # 记 export_log
    session.add(ExportLog(
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        export_type="cycle_result",
        filter_data={"cycle_id": cycle_id, "scope": "all" if scope is None else list(scope)[:20]},
        row_count=len(rows),
        file_name=file_name,
    ))
    session.commit()

    # HTTP header 不支持非 ASCII，用 RFC 5987 编码中文文件名
    encoded_name = quote(file_name)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )
