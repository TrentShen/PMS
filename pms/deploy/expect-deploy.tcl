#!/usr/bin/expect -f
# PMS 绩效管理系统 · 生产环境 Expect 部署脚本
# 参考招聘系统 deploy/expect-deploy.tcl 实现
# 每次执行均会交互式询问 SSH 密码，不读取环境变量

set timeout 300

# ---------- 服务器配置 ----------
set server "root@10.222.4.38"
set remote_dir "/opt/pms"
set project_root "/Users/trentshen/Documents/Kimi code - 工作区/hr/pms"
set local_tar "/tmp/pms-deploy.tar.gz"

# ---------- 1. 获取 SSH 密码 ----------
# 优先从环境变量读取（供自动化调用），否则交互式询问
if {[info exists env(DEPLOY_SSH_PASSWORD)] && $env(DEPLOY_SSH_PASSWORD) ne ""} {
    set password $env(DEPLOY_SSH_PASSWORD)
} else {
    send_user "请输入 ${server} 的 SSH 密码: "
    stty -echo
    expect_user -re "(.*)\n"
    stty echo
    set password $expect_out(1,string)
    send_user "\n"
}

# ---------- 2. 本地打包 ----------
send_user "\n"
send_user "📦 正在打包 PMS 项目...\n"
# 排除 .git、依赖、环境文件、证书，避免上传不必要或敏感文件
set build_cmd "COPYFILE_DISABLE=1 tar czf ${local_tar} --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' --exclude='.DS_Store' --exclude='*.pyc' --exclude='.env' --exclude='.env.prod' --exclude='certs' --exclude='._*' -C '${project_root}' ."
spawn bash -c $build_cmd
expect eof

# ---------- 3. 创建远程目录 ----------
send_user "\n"
send_user "📁 确保远程目录 ${remote_dir} 存在...\n"
spawn ssh ${server}
expect {
    "password:" { send "$password\r" }
    "yes/no" { send "yes\r"; expect "password:"; send "$password\r" }
}
expect "#"
send "mkdir -p ${remote_dir}\r"
expect "#"
send "exit\r"
expect eof

# ---------- 4. 上传部署包 ----------
send_user "\n"
send_user "⬆️  上传部署包到 ${server}:${remote_dir}...\n"
spawn scp ${local_tar} ${server}:${remote_dir}/pms-deploy.tar.gz
expect {
    "password:" { send "$password\r"; exp_continue }
    "yes/no" { send "yes\r"; exp_continue }
    eof
}

# ---------- 5. 远程执行部署 ----------
send_user "\n"
send_user "🔧 在远程服务器执行部署...\n"
spawn ssh ${server}
expect {
    "password:" { send "$password\r" }
    "yes/no" { send "yes\r"; expect "password:"; send "$password\r" }
}
expect "#"

# 备份服务器上的敏感配置文件（.env.prod 和 certs）
send "cd ${remote_dir} && cp -f deploy/.env.prod /tmp/pms-env-prod.bak 2>/dev/null || true\r"
expect "#"
send "cp -rf deploy/certs /tmp/pms-certs.bak 2>/dev/null || true\r"
expect "#"

# 解压覆盖
send "cd ${remote_dir} && tar xzf pms-deploy.tar.gz\r"
expect "#"

# 恢复敏感配置文件
send "cp -f /tmp/pms-env-prod.bak deploy/.env.prod 2>/dev/null || true\r"
expect "#"
send "cp -rf /tmp/pms-certs.bak deploy/certs 2>/dev/null || true\r"
expect "#"

# 设置脚本可执行权限
send "chmod +x ${remote_dir}/deploy/remote-deploy.sh\r"
expect "#"

# 执行远程部署脚本
send "bash ${remote_dir}/deploy/remote-deploy.sh\r"
expect {
    -exact {🚀 PMS 部署完成} {}
    -exact {[ERROR]} { puts "\n\n部署脚本报告错误"; exit 1 }
    timeout { puts "\n\n⏱️  部署脚本执行超时"; exit 1 }
}

send "exit\r"
expect eof

# ---------- 6. 清理本地临时文件 ----------
send_user "\n"
send_user "🧹 清理本地临时文件...\n"
file delete ${local_tar}
send_user "✅ 本地部署流程结束\n"
