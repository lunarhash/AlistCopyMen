# Alist File Monitor

一个用于监控 Alist 存储系统中文件变化的自动化工具。它可以自动将文件从源目录复制到目标目录，并通过 Discord Webhook 发送通知。

## 特性

- 自动监控源目录中的新文件
- 自动复制文件到目标目录
- 可选择在复制后删除源文件
- 文件完整性检查，确保只复制已完成下载的文件
- Discord 通知支持，实时了解文件处理状态
- 支持 Token 和用户名/密码认证
- 支持 Docker 部署

## 安装

### 方法一：直接运行

1. 克隆仓库：
```bash
git clone https://github.com/lunarhash/AlistCopyMen
cd alist-file-monitor
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

### 方法二：Docker 部署（推荐）

#### 使用 Docker Compose（最简单）

1. 创建项目目录：
```bash
mkdir alist-monitor && cd alist-monitor
```

2. 创建 `docker-compose.yml`：
```yaml
version: '3'
services:
  alist-monitor:
    image: python:3.9-slim
    container_name: alist-monitor
    restart: unless-stopped
    volumes:
      - ./config.json:/app/config.json
      - ./logs:/app/logs
    working_dir: /app
    command: >
      bash -c "pip install -r requirements.txt && python file_moverv1.0.py"
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

3. 创建配置文件 `config.json`：
```json
{
    "alist": {
        "url": "https://your-alist-server.com",
        "token": "your-alist-token",
        "username": "admin",
        "password": "your-password"
    },
    "monitor": {
        "source_path": "/source",
        "dest_path": "/destination",
        "check_interval": 30,
        "delete_source": true
    },
    "notification": {
        "discord_webhook": "your-discord-webhook-url",
        "notify_on_copy": true,
        "notify_on_delete": true,
        "notify_on_error": true
    }
}
```

4. 启动容器：
```bash
docker-compose up -d
```

5. 查看日志：
```bash
docker-compose logs -f
```

#### 使用 Dockerfile（自定义构建）

1. 创建 Dockerfile：
```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY requirements.txt .
COPY file_moverv1.0.py .
COPY config.example.json config.json

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置Python输出不缓冲
ENV PYTHONUNBUFFERED=1

# 创建日志目录
RUN mkdir -p /app/logs

# 运行脚本
CMD ["python", "file_moverv1.0.py"]
```

2. 构建镜像：
```bash
docker build -t alist-monitor .
```

3. 运行容器：
```bash
docker run -d \
  --name alist-monitor \
  --restart unless-stopped \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/logs:/app/logs \
  alist-monitor
```

### Docker 部署注意事项

1. 配置文件：
   - 确保 `config.json` 中的路径使用正斜杠 `/`
   - 配置文件会以卷的形式挂载到容器中
   - 修改配置后需要重启容器：`docker-compose restart`

2. 日志管理：
   - 日志文件存储在 `./logs` 目录
   - 可以通过 `docker-compose logs` 查看
   - 日志自动轮转，最大保留3个文件，每个10MB

3. 容器管理：
   - 启动：`docker-compose up -d`
   - 停止：`docker-compose down`
   - 重启：`docker-compose restart`
   - 查看日志：`docker-compose logs -f`
   - 查看状态：`docker-compose ps`

4. 故障排除：
   - 检查配置文件权限：确保容器可以读取
   - 检查日志目录权限：确保容器可以写入
   - 检查网络连接：确保可以访问 Alist 服务器
   - 如果容器启动失败，查看详细日志：`docker logs alist-monitor`

5. 更新：
   ```bash
   # 拉取最新代码
   git pull
   
   # 重新构建镜像
   docker-compose build
   
   # 重启服务
   docker-compose up -d
   ```

6. 备份：
   - 定期备份 `config.json`
   - 可以使用 Docker 卷备份工具
   - 重要数据建议使用外部存储

7. 监控：
   - 使用 Discord 通知监控运行状态
   - 可以配置 Docker 的健康检查
   - 推荐使用容器监控工具（如 Portainer）

## 配置

在运行脚本之前，需要创建 `config.json` 配置文件：

```json
{
    "alist": {
        "url": "https://your-alist-server.com",
        "token": "your-alist-token",
        "username": "admin",
        "password": "your-password"
    },
    "monitor": {
        "source_path": "/source",
        "dest_path": "/destination",
        "check_interval": 30,
        "delete_source": true
    },
    "notification": {
        "discord_webhook": "your-discord-webhook-url",
        "notify_on_copy": true,
        "notify_on_delete": true,
        "notify_on_error": true
    }
}
```

### 配置说明

#### Alist 配置
- `url`: Alist 服务器地址
- `token`: Alist 管理员 token（推荐使用）
- `username`: 管理员用户名（如果不使用 token）
- `password`: 管理员密码（如果不使用 token）

#### 监控配置
- `source_path`: 源目录路径
- `dest_path`: 目标目录路径
- `check_interval`: 检查间隔（秒）
- `delete_source`: 是否在复制后删除源文件

#### 通知配置
- `discord_webhook`: Discord Webhook URL
- `notify_on_copy`: 是否在复制文件时发送通知
- `notify_on_delete`: 是否在删除文件时发送通知
- `notify_on_error`: 是否在发生错误时发送通知

## 运行

```bash
python file_moverv1.0.py
```

## 通知说明

脚本会发送以下类型的通知到 Discord：

- 启动通知：显示监控配置信息
- 复制通知：显示文件名、大小和路径
- 删除通知：显示被删除的文件
- 等待通知：文件下载/写入未完成
- 成功通知：操作完成
- 错误通知：发生错误或异常
- 警告通知：网络问题等
- 停止通知：显示处理文件统计

## 安全性建议

1. 使用 Alist Token 而不是用户名密码
2. 不要将包含敏感信息的配置文件提交到版本控制系统
3. 确保 Discord Webhook URL 不被泄露

## 注意事项

1. 脚本会检查文件完整性，只有当文件完全下载完成后才会进行复制
2. 如果启用了删除源文件功能，请确保备份重要数据
3. 建议先在测试环境中运行脚本，确认配置正确

## 常见问题

1. 文件复制失败
   - 检查网络连接
   - 确认文件权限
   - 查看 Discord 通知中的错误信息

2. 无法收到 Discord 通知
   - 验证 Webhook URL 是否正确
   - 检查网络连接
   - 确认通知配置已启用

3. 脚本无法连接到 Alist
   - 确认 Alist 服务器地址正确
   - 验证 Token 或用户名密码
   - 检查网络连接

## 许可证

MIT License
