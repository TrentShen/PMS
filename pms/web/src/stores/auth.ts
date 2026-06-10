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
  has_hr_permission?: boolean;
  has_subordinates?: boolean;
}

interface AuthState {
  token: string | null;
  user: CurrentUser | null;
  setAuth: (token: string, user: CurrentUser) => void;
  clear: () => void;
}

const TOKEN_KEY = "pms_token";
const USER_KEY = "pms_user";

function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSet(key: string, val: string) {
  try { localStorage.setItem(key, val); } catch { /* noop */ }
}
function safeRemove(key: string) {
  try { localStorage.removeItem(key); } catch { /* noop */ }
}

function loadUser(): CurrentUser | null {
  const raw = safeGet(USER_KEY);
  return raw ? (JSON.parse(raw) as CurrentUser) : null;
}

export const useAuth = create<AuthState>((set) => ({
  token: safeGet(TOKEN_KEY),
  user: loadUser(),
  setAuth: (token, user) => {
    safeSet(TOKEN_KEY, token);
    safeSet(USER_KEY, JSON.stringify(user));
    set({ token, user });
  },
  clear: () => {
    safeRemove(TOKEN_KEY);
    safeRemove(USER_KEY);
    set({ token: null, user: null });
  },
}));
