// 登录页：列出所有 mock 身份，点击即以该身份登录
// Sprint 1 企微 OAuth 接入后，本页只在未从企微入口时显示
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, List, Tag, Typography, message } from "antd";
import { api } from "@/services/api";
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

export default function Login() {
  const [users, setUsers] = useState<MockUser[]>([]);
  const [loadingUid, setLoadingUid] = useState<string | null>(null);
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<MockUser[]>("/v1/auth/mock-users").then((r) => setUsers(r.data));
  }, []);

  async function loginAs(uid: string) {
    setLoadingUid(uid);
    try {
      const r = await api.post("/v1/auth/mock-login", { wecom_userid: uid });
      setAuth(r.data.token, r.data.user);
      message.success(`已登录为 ${r.data.user.name}`);
      navigate("/");
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "登录失败");
    } finally {
      setLoadingUid(null);
    }
  }

  return (
    <div style={{ maxWidth: 600, margin: "48px auto", padding: 16 }}>
      <Card title="绩效管理系统 · 登录（开发 Mock）">
        <Typography.Paragraph type="secondary">
          企微 OAuth 尚未接入，选择一个身份即可进入系统进行功能测试。
        </Typography.Paragraph>
        <List
          dataSource={users}
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
