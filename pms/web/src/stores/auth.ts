// 全局登录状态：token + 当前用户
// 用 Zustand 而非 Context，写起来最简；刷新后从 localStorage 恢复
import { create } from "zustand";

export interface CurrentUser {
  id: number;
  wecom_userid: string;
  name: string;
  role: string;
  position?: string | null;
  leader_userid?: string | null;
  // HR 部门 Leader 虽然 role=dept_leader 但有 HR 权限
  has_hr_permission?: boolean;
}

interface AuthState {
  token: string | null;
  user: CurrentUser | null;
  setAuth: (token: string, user: CurrentUser) => void;
  clear: () => void;
}

const TOKEN_KEY = "pms_token";
const USER_KEY = "pms_user";

function loadUser(): CurrentUser | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as CurrentUser) : null;
}

export const useAuth = create<AuthState>((set) => ({
  token: localStorage.getItem(TOKEN_KEY),
  user: loadUser(),
  setAuth: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, user });
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, user: null });
  },
}));
