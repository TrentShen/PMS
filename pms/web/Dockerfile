# 前端构建镜像（多阶段：Node 构建 → 产出 dist 文件）
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# 最终阶段仅携带构建产物
FROM alpine
COPY --from=builder /app/dist /dist
