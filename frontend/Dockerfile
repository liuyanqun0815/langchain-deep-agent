# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 运行阶段：serve 静态服务
FROM node:20-alpine

RUN npm install -g serve

WORKDIR /app
COPY --from=builder /app/dist ./dist

EXPOSE 80
CMD ["serve", "-s", "dist", "-l", "80"]
