from __future__ import annotations

# 显式导入所有模型，保证 Alembic autogenerate 能发现
# 添加新表时必须在此处 import
from pms.database.models.audit import AuditLog, ExportLog, NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import (
    CycleStatus,
    EvalType,
    ParticipantStatus,
    PerfLevel,
    Role,
    ValueGrade,
)
from pms.database.models.calibration import CalibrationRecord, CycleApproval
from pms.database.models.evaluation import Evaluation
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.objective import Objective
from pms.database.models.peer import AnonymousFeedback, PeerEvaluation, PeerInvitation
from pms.database.models.user import Department, User

__all__ = [
    "AuditLog",
    "ExportLog",
    "NotificationLog",
    "CalibrationRecord",
    "CycleApproval",
    "FeedbackRecord",
    "CycleParticipant",
    "PerformanceCycle",
    "Evaluation",
    "Objective",
    "PeerInvitation",
    "PeerEvaluation",
    "AnonymousFeedback",
    "Department",
    "User",
    "CycleStatus",
    "EvalType",
    "ParticipantStatus",
    "PerfLevel",
    "Role",
    "ValueGrade",
]
