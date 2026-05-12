import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Result, Spin } from "antd";
import { api } from "@/services/api";

// 企微 OAuth 回调着陆页：从 URL 取 code，转发到后端换 JWT
// Sprint 1 会完成后端签发 JWT + 种 cookie + 跳转到首页
export default function AuthCallback() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const code = params.get("code");
    if (!code) {
      setStatus("error");
      setMessage("未收到企微 code");
      return;
    }
    api.get("/v1/auth/callback", { params: { code } })
      .then((res) => {
        setStatus("ok");
        setMessage(res.data.message ?? "登录成功");
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err?.message ?? "登录失败");
      });
  }, [params]);

  if (status === "loading") return <Spin style={{ marginTop: 100 }} />;
  return (
    <Result
      status={status === "ok" ? "success" : "error"}
      title={status === "ok" ? "已收到回调" : "登录失败"}
      subTitle={message}
    />
  );
}
