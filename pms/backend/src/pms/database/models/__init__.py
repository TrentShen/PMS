from __future__ import annotations

# 显式导入所有模型，保证 Alembic autogenerate 能发现
# 添加新表时必须在此处 import
from pms.database.models.audit import AuditLog, ExportLog, NotificationLog
from pms.database.models.calibration import CalibrationRecord, CycleApproval
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import (
    CycleStatus,
    EvalType,
    ObjectiveCycleStatus,
    ParticipantStatus,
    PerfLevel,
    ProbationObjectiveStatus,
    ProbationPlanStatus,
    ProbationResult,
    Role,
    ValueGrade,
)
from pms.database.models.evaluation import Evaluation
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.historical_performance import HistoricalPerformanceResult
from pms.database.models.objective import Objective
from pms.database.models.objective_cycle import ObjectiveCycle
from pms.database.models.objective_cycle_participant import ObjectiveCycleParticipant
from pms.database.models.objective_revision import ObjectiveRevision
from pms.database.models.peer import AnonymousFeedback, PeerEvaluation, PeerInvitation
from pms.database.models.probation import ProbationObjective, ProbationPlan
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
    "ObjectiveCycle",
    "ObjectiveCycleParticipant",
    "HistoricalPerformanceResult",
    "Evaluation",
    "Objective",
    "ObjectiveRevision",
    "ProbationObjective",
    "ProbationPlan",
    "PeerInvitation",
    "PeerEvaluation",
    "AnonymousFeedback",
    "Department",
    "User",
    "CycleStatus",
    "EvalType",
    "ObjectiveCycleStatus",
    "ParticipantStatus",
    "PerfLevel",
    "ProbationObjectiveStatus",
    "ProbationPlanStatus",
    "ProbationResult",
    "Role",
    "ValueGrade",
]
