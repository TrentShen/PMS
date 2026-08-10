import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { useAuth } from "@/stores/auth";
import ProtectedRoute from "./ProtectedRoute";

// 登录页替身：把 search 渲染出来，方便断言 redirect 参数
function LoginStub() {
  const location = useLocation();
  return <div>登录页{location.search}</div>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginStub />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/hr/users" element={<div>受保护内容</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuth.setState({ token: null, user: null });
  });

  it("未登录时跳转 /login 并带 redirect 参数（含 query）", () => {
    renderAt("/hr/users?tab=1");
    const redirect = encodeURIComponent("/hr/users?tab=1");
    expect(screen.getByText(`登录页?redirect=${redirect}`)).toBeInTheDocument();
    expect(screen.queryByText("受保护内容")).not.toBeInTheDocument();
  });

  it("已登录时渲染子路由内容", () => {
    useAuth.setState({ token: "fake-token" });
    renderAt("/hr/users");
    expect(screen.getByText("受保护内容")).toBeInTheDocument();
  });
});
