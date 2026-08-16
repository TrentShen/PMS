// 登录页：在企微内 → 跳 OAuth 授权；非企微 → mock 身份列表
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Card, Empty, List, Result, Tag, Typography, message } from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";


interface MockUser {
  wecom_userid: string;
  name: string;
  role: string;
  position: string | null;
}

const ROLE_COLOR: Record<string, string> = {
  super_admin: "purple",
  hrbp: "magenta",
  dept_leader: "geekblue",
  direct_leader: "blue",
  employee: "green",
};

const ROLE_LABEL: Record<string, string> = {
  super_admin: "超级管理员",
  hrbp: "HR",
  dept_leader: "部门 Leader",
  direct_leader: "直属上级",
  employee: "员工",
};

/** 判断是否在企微客户端内 */
function isWeCom(): boolean {
  return /wxwork/i.test(navigator.userAgent);
}

// 企微 OAuth 跳转会离开本站，redirect 参数无法随 URL 带回，先存 sessionStorage，
// AuthCallback 登录成功后取出回跳（key 与 AuthCallback 保持一致）
const REDIRECT_KEY = "pms_auth_redirect";

/** 只允许站内路径，防开放重定向 */
function safeRedirect(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

export default function Login() {
  const [users, setUsers] = useState<MockUser[]>([]);
  const [loadingUid, setLoadingUid] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [entryError, setEntryError] = useState("");
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const redirect = safeRedirect(params.get("redirect"));

  useEffect(() => {
    if (isWeCom()) {
      // 企微环境：跳转 OAuth 授权页
      try {
        sessionStorage.setItem(REDIRECT_KEY, redirect);
      } catch {
        /* noop */
      }
      api.get("/v1/auth/entry", { params: { is_wecom: true } }).then((r) => {
        window.location.href = r.data.redirect;
      }).catch((e) => {
        // entry 失败说明企微 OAuth 配置/网络异常，不能静默落到 mock 页
        //（生产上会把 OAuth 故障伪装成开发页）
        setEntryError(formatError(e, "企业微信登录入口获取失败"));
        setChecking(false);
      });
      return;
    }
    // 非企微环境：展示 mock 登录
    setChecking(false);
    api
      .get<MockUser[]>("/v1/auth/mock-users")
      .then((r) => setUsers(r.data))
      .catch((e) => message.error(formatError(e, "加载测试账号失败")));
  }, [redirect]);

  async function loginAs(uid: string) {
    setLoadingUid(uid);
    try {
      const r = await api.post("/v1/auth/mock-login", { wecom_userid: uid });
      setAuth(r.data.token, r.data.user);
      message.success(`已登录为 ${r.data.user.name}`);
      navigate(redirect);
    } catch (e) {
      message.error(formatError(e, "登录失败"));
    } finally {
      setLoadingUid(null);
    }
  }

  if (checking) {
    return (
      <div style={{ maxWidth: 400, margin: "120px auto", textAlign: "center" }}>
        正在跳转企业微信登录...
      </div>
    );
  }

  if (entryError) {
    return (
      <Result
        status="error"
        title="企业微信登录失败"
        subTitle={entryError}
        extra={
          <Button type="primary" onClick={() => window.location.reload()}>
            重试
          </Button>
        }
      />
    );
  }

  return (
    <div style={{ maxWidth: 600, margin: "48px auto", padding: 16 }}>
      <Card title="MO绩效 · 登录（开发 Mock）">
        <Typography.Paragraph type="secondary">
          企微 OAuth 尚未接入，选择一个身份即可进入系统进行功能测试。
        </Typography.Paragraph>
        <List
          dataSource={users}
          locale={{ emptyText: <Empty description="暂无可用的测试身份" /> }}
          renderItem={(u) => (
            <List.Item
              actions={[
                <Button
                  key="login"
                  type="primary"
                  loading={loadingUid === u.wecom_userid}
                  onClick={() => loginAs(u.wecom_userid)}
                >
                  以此身份进入
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <>
                    {u.name}{" "}
                    <Tag color={ROLE_COLOR[u.role] ?? "default"}>
                      {ROLE_LABEL[u.role] ?? u.role}
                    </Tag>
                  </>
                }
                description={u.position}
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
