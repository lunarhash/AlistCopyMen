FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置Python输出不缓冲
ENV PYTHONUNBUFFERED=1

# 创建日志目录
RUN mkdir -p /app/logs

# 复制项目文件
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 运行脚本
CMD ["python", "file_moverv1.0.py"]
