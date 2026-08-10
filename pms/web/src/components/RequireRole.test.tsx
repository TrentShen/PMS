import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { useAuth, type CurrentUser } from "@/stores/auth";
import RequireRole from "./RequireRole";

function makeUser(role: string): CurrentUser {
  return {
    id: 1,
    wecom_userid: "u001",
    name: "张三",
    role,
    base_role: role,
  };
}

function renderAt(roles: string[]) {
  return render(
    <MemoryRouter initialEntries={["/hr"]}>
      <Routes>
        <Route element={<RequireRole roles={roles} fallback="forbid" />}>
          <Route path="/hr" element={<div>HR 控制台</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("RequireRole", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuth.setState({ token: null, user: null });
  });

  it("角色不匹配时渲染 403 且有「返回首页」按钮", () => {
    useAuth.setState({ token: "t", user: makeUser("employee") });
    renderAt(["hrbp", "super_admin"]);
    expect(screen.getByText("403")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "返回首页" })).toBeInTheDocument();
    expect(screen.queryByText("HR 控制台")).not.toBeInTheDocument();
  });

  it("角色匹配时渲染子内容", () => {
    useAuth.setState({ token: "t", user: makeUser("hrbp") });
    renderAt(["hrbp", "super_admin"]);
    expect(screen.getByText("HR 控制台")).toBeInTheDocument();
  });
});
