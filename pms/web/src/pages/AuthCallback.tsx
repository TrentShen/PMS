// 企微 OAuth 回调着陆页：从 URL 取 code，转发到后端换 JWT
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Result, Spin } from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

// 与 Login 页一致：OAuth 跳转前暂存的登录后回跳地址
const REDIRECT_KEY = "pms_auth_redirect";

/** 取回跳地址：优先 sessionStorage（OAuth 场景），仅允许站内路径 */
function takeRedirect(): string {
  let raw: string | null = null;
  try {
    raw = sessionStorage.getItem(REDIRECT_KEY);
    sessionStorage.removeItem(REDIRECT_KEY);
  } catch {
    /* noop */
  }
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

export default function AuthCallback() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const code = params.get("code");
    if (!code) {
      setStatus("error");
      setMessage("未收到企微 code");
      return;
    }
    // state 由后端 /auth/entry 签发，回调时原样带回用于一次性校验
    const state = params.get("state") ?? "";
    api.get("/v1/auth/callback", { params: { code, state } })
      .then((res) => {
        const { token, user } = res.data;
        setAuth(token, user);
        setStatus("ok");
        setMessage(`欢迎，${user.name}`);
        timer = setTimeout(() => navigate(takeRedirect(), { replace: true }), 800);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err?.response?.data?.detail ?? err?.message ?? "登录失败");
      });
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [params]);

  if (status === "loading") return <Spin size="large" style={{ display: "block", marginTop: 120 }} />;
  return (
    <Result
      status={status === "ok" ? "success" : "error"}
      title={status === "ok" ? "登录成功" : "登录失败"}
      subTitle={message}
    />
  );
}
