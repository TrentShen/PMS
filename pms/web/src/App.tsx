// 路由
// 分两层守卫：
//   1. ProtectedRoute —— 必须登录
//   2. RequireRole    —— 按角色限制访问某些页面
// 所有页面走 React.lazy 按路由分包，避免图表等大依赖进入首屏 chunk
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";
import AppLayout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import RequireRole from "@/components/RequireRole";

const Login = lazy(() => import("@/pages/Login"));
const AuthCallback = lazy(() => import("@/pages/AuthCallback"));
const Home = lazy(() => import("@/pages/Home"));
const HrDashboard = lazy(() => import("@/pages/HrDashboard"));
const MyObjectives = lazy(() => import("@/pages/MyObjectives"));
const ObjectiveCycleDetail = lazy(() => import("@/pages/ObjectiveCycleDetail"));
const ObjectiveCycleList = lazy(() => import("@/pages/ObjectiveCycleList"));
const SelfEval = lazy(() => import("@/pages/SelfEval"));
const LeaderEval = lazy(() => import("@/pages/LeaderEval"));
const LeaderEvalDetail = lazy(() => import("@/pages/LeaderEvalDetail"));
const HrConsole = lazy(() => import("@/pages/HrConsole"));
const AdminUsers = lazy(() => import("@/pages/AdminUsers"));
const PeerTasks = lazy(() => import("@/pages/PeerTasks"));
const PeerReview = lazy(() => import("@/pages/PeerReview"));
const AnonymousFeedbackPage = lazy(() => import("@/pages/AnonymousFeedback"));
const Calibration = lazy(() => import("@/pages/Calibration"));
const NineGrid = lazy(() => import("@/pages/NineGrid"));
const Notifications = lazy(() => import("@/pages/Notifications"));
const Feedback = lazy(() => import("@/pages/Feedback"));
const History = lazy(() => import("@/pages/History"));
const Trend = lazy(() => import("@/pages/Trend"));
const Probation = lazy(() => import("@/pages/Probation"));
const ProbationDetail = lazy(() => import("@/pages/ProbationDetail"));

// 集中定义角色分组，避免各处散落字符串
export const ROLE = {
  HR: ["hrbp", "super_admin"],
  LEADER: ["dept_leader", "direct_leader", "hrbp", "super_admin"],
  ADMIN: ["super_admin", "hrbp"],
} as const;

export default function App() {
  return (
    <Suspense
      fallback={
        <div
          style={{ display: "flex", justifyContent: "center", paddingTop: 120 }}
        >
          <Spin size="large" />
        </div>
      }
    >
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            {/* 所有登录用户可见 */}
            <Route path="/" element={<Home />} />
            <Route path="/self/:cycleId" element={<SelfEval />} />
            <Route
              path="/objectives/:objectiveCycleId"
              element={<MyObjectives />}
            />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/peer" element={<PeerTasks />} />
            <Route path="/anonymous" element={<AnonymousFeedbackPage />} />
            {/* 反馈：员工看自己 /feedback/:cycleId 全员开放 */}
            <Route path="/feedback/:cycleId" element={<Feedback />} />

            {/* 历史绩效/趋势：仅 Leader/HR 可见（普通员工含自己的也不可见） */}
            <Route
              element={
                <RequireRole
                  roles={[...ROLE.LEADER]}
                  fallback="forbid"
                  allowHrPermission
                />
              }
            >
              <Route path="/history" element={<History />} />
              <Route path="/trend" element={<Trend />} />
              <Route path="/trend/:userId" element={<Trend />} />
            </Route>

            {/* 上级写别人 /feedback/:cycleId/:userId：仅 Leader/HR（含 HR 部门 Leader） */}
            <Route
              element={
                <RequireRole
                  roles={[...ROLE.LEADER]}
                  fallback="forbid"
                  allowHrPermission
                />
              }
            >
              <Route path="/feedback/:cycleId/:userId" element={<Feedback />} />
            </Route>

            {/* 试用期详情：员工可看/填写自己的；上级/HR 看下属的（后端按 scope 控制） */}
            <Route path="/probation/:userId" element={<ProbationDetail />} />

            {/* 仅 Leader/HR 可见 */}
            <Route
              element={
                <RequireRole roles={[...ROLE.LEADER]} fallback="forbid" />
              }
            >
              <Route path="/leader" element={<LeaderEval />} />
              <Route
                path="/leader/:cycleId/users/:userId"
                element={<LeaderEvalDetail />}
              />
              <Route path="/peer-review" element={<PeerReview />} />
            </Route>

            {/* 校准：dept_leader/HR + HR 部门 Leader（与后端口径一致，direct_leader 无权限） */}
            <Route
              element={
                <RequireRole
                  roles={["dept_leader", ...ROLE.HR]}
                  fallback="forbid"
                  allowHrPermission
                />
              }
            >
              <Route path="/calibration" element={<Calibration />} />
              <Route path="/nine-grid" element={<NineGrid />} />
            </Route>

            {/* HR 管理台：hrbp/super_admin + HR 部门 Leader */}
            <Route
              element={
                <RequireRole
                  roles={[...ROLE.HR]}
                  fallback="forbid"
                  allowHrPermission
                />
              }
            >
              <Route path="/hr" element={<HrConsole />} />
              <Route path="/hr/dashboard" element={<HrDashboard />} />
              <Route
                path="/objective-cycles"
                element={<ObjectiveCycleList />}
              />
              <Route
                path="/objective-cycles/:id"
                element={<ObjectiveCycleDetail />}
              />
            </Route>

            {/* 试用期管理：Leader/HR 可见 */}
            <Route
              element={
                <RequireRole
                  roles={[...ROLE.HR, ...ROLE.LEADER]}
                  fallback="forbid"
                  allowHrPermission
                />
              }
            >
              <Route path="/probation" element={<Probation />} />
            </Route>

            {/* 仅超级管理员可见 */}
            <Route
              element={
                <RequireRole
                  roles={[...ROLE.ADMIN]}
                  fallback="forbid"
                  allowHrPermission
                />
              }
            >
              <Route path="/admin/users" element={<AdminUsers />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
