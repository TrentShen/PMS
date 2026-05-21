// 企微 OAuth 回调着陆页：从 URL 取 code，转发到后端换 JWT
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Result, Spin } from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

export default function AuthCallback() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  useEffect(() => {
    const code = params.get("code");
    if (!code) {
      setStatus("error");
      setMessage("未收到企微 code");
      return;
    }
    api.get("/v1/auth/callback", { params: { code } })
      .then((res) => {
        const { token, user } = res.data;
        setAuth(token, user);
        setStatus("ok");
        setMessage(`欢迎，${user.name}`);
        setTimeout(() => navigate("/", { replace: true }), 800);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err?.response?.data?.detail ?? err?.message ?? "登录失败");
      });
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
