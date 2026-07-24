// 路由
// 分两层守卫：
//   1. ProtectedRoute —— 必须登录
//   2. RequireRole    —— 按角色限制访问某些页面
import { Navigate, Route, Routes } from "react-router-dom";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import AppLayout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import RequireRole from "@/components/RequireRole";
import Home from "@/pages/Home";
import HrDashboard from "@/pages/HrDashboard";
import MyObjectives from "@/pages/MyObjectives";
import ObjectiveCycleDetail from "@/pages/ObjectiveCycleDetail";
import ObjectiveCycleList from "@/pages/ObjectiveCycleList";
import SelfEval from "@/pages/SelfEval";
import LeaderEval from "@/pages/LeaderEval";
import LeaderEvalDetail from "@/pages/LeaderEvalDetail";
import HrConsole from "@/pages/HrConsole";
import AdminUsers from "@/pages/AdminUsers";
import PeerTasks from "@/pages/PeerTasks";
import AnonymousFeedbackPage from "@/pages/AnonymousFeedback";
import Calibration from "@/pages/Calibration";
import Notifications from "@/pages/Notifications";
import Feedback from "@/pages/Feedback";
import History from "@/pages/History";
import Trend from "@/pages/Trend";
import Probation from "@/pages/Probation";
import ProbationDetail from "@/pages/ProbationDetail";

// 集中定义角色分组，避免各处散落字符串
export const ROLE = {
  HR: ["hrbp", "super_admin"],
  LEADER: ["dept_leader", "direct_leader", "hrbp", "super_admin"],
  ADMIN: ["super_admin", "hrbp"],
} as const;

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {/* 所有登录用户可见 */}
          <Route path="/" element={<Home />} />
          <Route path="/self/:cycleId" element={<SelfEval />} />
          <Route path="/objectives/:objectiveCycleId" element={<MyObjectives />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/peer" element={<PeerTasks />} />
          <Route path="/anonymous" element={<AnonymousFeedbackPage />} />
          <Route path="/history" element={<History />} />
          <Route path="/trend" element={<Trend />} />
          <Route path="/trend/:userId" element={<Trend />} />
          {/* 反馈：员工看自己 /feedback/:cycleId；上级写别人 /feedback/:cycleId/:userId */}
          <Route path="/feedback/:cycleId" element={<Feedback />} />
          <Route path="/feedback/:cycleId/:userId" element={<Feedback />} />

          {/* 试用期详情：员工可看/填写自己的；上级/HR 看下属的（后端按 scope 控制） */}
          <Route path="/probation/:userId" element={<ProbationDetail />} />

          {/* 仅 Leader/HR 可见 */}
          <Route element={<RequireRole roles={[...ROLE.LEADER]} fallback="forbid" />}>
            <Route path="/leader" element={<LeaderEval />} />
            <Route path="/leader/:cycleId/users/:userId" element={<LeaderEvalDetail />} />
          </Route>

          {/* 校准：dept_leader/HR + HR 部门 Leader（与后端口径一致，direct_leader 无权限） */}
          <Route element={<RequireRole roles={["dept_leader", ...ROLE.HR]} fallback="forbid" allowHrPermission />}>
            <Route path="/calibration" element={<Calibration />} />
          </Route>

          {/* HR 管理台：hrbp/super_admin + HR 部门 Leader */}
          <Route element={<RequireRole roles={[...ROLE.HR]} fallback="forbid" allowHrPermission />}>
            <Route path="/hr" element={<HrConsole />} />
            <Route path="/hr/dashboard" element={<HrDashboard />} />
            <Route path="/objective-cycles" element={<ObjectiveCycleList />} />
            <Route path="/objective-cycles/:id" element={<ObjectiveCycleDetail />} />
          </Route>

          {/* 试用期管理：Leader/HR 可见 */}
          <Route element={<RequireRole roles={[...ROLE.HR, ...ROLE.LEADER]} fallback="forbid" allowHrPermission />}>
            <Route path="/probation" element={<Probation />} />
          </Route>

          {/* 仅超级管理员可见 */}
          <Route element={<RequireRole roles={[...ROLE.ADMIN]} fallback="forbid" allowHrPermission />}>
            <Route path="/admin/users" element={<AdminUsers />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
