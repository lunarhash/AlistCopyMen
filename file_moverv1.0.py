import time
import requests
import logging
import json
import os
import sys

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(message)s',
                   datefmt='%Y-%m-%d %H:%M:%S')

def load_config(config_path):
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 验证必要的配置项
        required_fields = {
            'alist': ['url'],
            'monitor': ['source_path', 'dest_path', 'check_interval']
        }
        
        for section, fields in required_fields.items():
            if section not in config:
                raise ValueError(f"配置文件缺少 {section} 部分")
            for field in fields:
                if field not in config[section]:
                    raise ValueError(f"配置文件缺少 {section}.{field} 配置项")
        
        return config
    except json.JSONDecodeError as e:
        logging.error(f"配置文件格式错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"加载配置文件失败: {str(e)}")
        sys.exit(1)

class DiscordNotifier:
    def __init__(self, webhook_url, notify_config):
        self.webhook_url = webhook_url
        self.notify_config = notify_config
        
    def send_message(self, content, is_error=False):
        """发送消息到Discord"""
        if not self.webhook_url:
            return
            
        # 根据配置决定是否发送通知
        if is_error and not self.notify_config.get('notify_on_error', True):
            return
            
        try:
            data = {
                "content": content,
                "username": "Alist File Monitor"
            }
            
            response = requests.post(self.webhook_url, json=data)
            if response.status_code != 204:
                logging.error(f"发送Discord通知失败: {response.text}")
        except Exception as e:
            logging.error(f"发送Discord通知时发生错误: {str(e)}")

class AlistFileManager:
    def __init__(self, base_url, token=None, username=None, password=None, notifier=None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = token
        self.notifier = notifier
        self.headers = {
            'Content-Type': 'application/json'
        }
        
        # 如果提供了token，直接使用
        if self.token:
            self.headers['Authorization'] = self.token
            logging.info("使用配置文件中的token")
            if self.notifier:
                self.notifier.send_message("🔑 使用配置文件中的token连接到Alist")
        else:
            # 否则尝试使用用户名和密码登录
            if not self.username or not self.password:
                raise ValueError("未提供token，且用户名或密码为空")
            self.login()

    def login(self):
        """登录获取管理员token"""
        try:
            url = f"{self.base_url}/api/auth/login"
            data = {
                "username": self.username,
                "password": self.password
            }
            response = requests.post(url, json=data)
            if response.status_code == 200:
                token = response.json().get('data', {}).get('token')
                if token:
                    self.headers['Authorization'] = token
                    logging.info("管理员登录成功")
                    if self.notifier:
                        self.notifier.send_message("✅ 管理员登录成功")
                    return True
                else:
                    error_msg = "登录成功但未获取到token"
                    logging.error(error_msg)
                    if self.notifier:
                        self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                    return False
            else:
                error_msg = f"登录失败: {response.text}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                return False
        except Exception as e:
            error_msg = f"登录时发生错误: {str(e)}"
            logging.error(error_msg)
            if self.notifier:
                self.notifier.send_message(f"❌ {error_msg}", is_error=True)
            return False

    def list_files(self, path):
        """列出指定路径下的所有文件"""
        try:
            url = f"{self.base_url}/api/fs/list"
            data = {
                "path": path,
                "password": "",
                "page": 1,
                "per_page": 0,
                "refresh": True
            }
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                content = response.json().get('data', {}).get('content', [])
                return {item['name']: item for item in content if not item.get('is_dir', False)}
            else:
                logging.error(f"列出文件失败: {response.text}")
                return {}
        except Exception as e:
            logging.error(f"列出文件时发生错误: {str(e)}")
            return {}

    def is_file_ready(self, path, filename, wait_time=60, check_interval=5):
        """
        检查文件是否已经下载完成并且可以安全复制
        
        参数:
            path: 文件所在目录
            filename: 文件名
            wait_time: 最长等待时间（秒）
            check_interval: 检查间隔（秒）
            
        返回:
            (bool, str): (是否准备好, 原因消息)
        """
        max_attempts = wait_time // check_interval
        last_size = None
        unchanged_count = 0
        required_unchanged = 3  # 文件大小需要连续3次保持不变
        
        for attempt in range(max_attempts):
            try:
                # 获取当前文件信息
                files = self.list_files(path)
                if filename not in files:
                    return False, "文件不存在"
                
                current_file = files[filename]
                current_size = current_file.get('size', 0)
                current_modified = current_file.get('modified', 0)
                
                # 如果是第一次检查
                if last_size is None:
                    last_size = current_size
                    continue
                
                # 检查文件大小是否变化
                if current_size == last_size:
                    unchanged_count += 1
                    if unchanged_count >= required_unchanged:
                        # 文件大小已经连续多次保持不变
                        file_size_mb = current_size / (1024 * 1024)
                        return True, f"文件大小 {file_size_mb:.2f}MB 已稳定"
                else:
                    # 文件大小发生变化，重置计数
                    unchanged_count = 0
                    if self.notifier:
                        self.notifier.send_message(
                            f"⏳ 文件 {filename} 仍在下载中...\n"
                            f"当前大小: {current_size / (1024 * 1024):.2f}MB\n"
                            f"等待文件下载完成..."
                        )
                
                last_size = current_size
                time.sleep(check_interval)
                
            except Exception as e:
                return False, f"检查文件状态时发生错误: {str(e)}"
        
        return False, f"等待超时（{wait_time}秒），文件可能仍在下载中"

    def copy_file(self, src_path, dst_path):
        """复制文件"""
        try:
            # 1. 确保源文件存在
            src_dir = '/'.join(src_path.split('/')[:-1])
            filename = src_path.split('/')[-1]
            dst_dir = '/'.join(dst_path.split('/')[:-1])
            
            files = self.list_files(src_dir)
            if filename not in files:
                error_msg = f"源文件不存在: {src_path}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                return False
            
            # 检查文件是否已经下载完成
            is_ready, message = self.is_file_ready(src_dir, filename)
            if not is_ready:
                error_msg = f"无法复制文件 {filename}: {message}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"⚠️ {error_msg}", is_error=True)
                return False
            
            file_size = files[filename].get('size', 0)
            file_size_mb = file_size / (1024 * 1024)
            
            # 2. 发送复制请求
            url = f"{self.base_url}/api/fs/copy"
            data = {
                "src_dir": src_dir,
                "dst_dir": dst_dir,
                "names": [filename]
            }
            
            logging.info(f"复制文件 {filename}")
            logging.info(f"从: {src_dir}")
            logging.info(f"到: {dst_dir}")
            
            if self.notifier and self.notifier.notify_config.get('notify_on_copy', True):
                self.notifier.send_message(
                    f"📋 开始复制文件\n"
                    f"文件名: {filename}\n"
                    f"大小: {file_size_mb:.2f}MB\n"
                    f"从: {src_dir}\n"
                    f"到: {dst_dir}"
                )
            
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code != 200:
                error_msg = f"复制请求失败: {response.text}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                return False
            
            response_json = response.json()
            if response_json.get('code') != 200:
                error_msg = f"复制失败: {response_json.get('message')}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                return False
            
            # 3. 等待文件出现在目标目录
            for attempt in range(10):  # 最多等待50秒
                time.sleep(5)
                dst_files = self.list_files(dst_dir)
                if filename in dst_files:
                    success_msg = f"文件复制成功: {filename}"
                    logging.info(success_msg)
                    if self.notifier and self.notifier.notify_config.get('notify_on_copy', True):
                        self.notifier.send_message(f"✅ {success_msg}")
                    return True
            
            error_msg = f"复制超时，文件未出现在目标目录: {filename}"
            logging.error(error_msg)
            if self.notifier:
                self.notifier.send_message(f"❌ {error_msg}", is_error=True)
            return False
            
        except Exception as e:
            error_msg = f"复制文件时发生错误: {str(e)}"
            logging.error(error_msg)
            if self.notifier:
                self.notifier.send_message(f"❌ {error_msg}", is_error=True)
            return False

    def delete_file(self, file_path):
        """删除文件"""
        try:
            url = f"{self.base_url}/api/fs/remove"
            data = {
                "dir": '/'.join(file_path.split('/')[:-1]),  # 获取目录路径
                "names": [file_path.split('/')[-1]]  # 获取文件名
            }
            
            filename = file_path.split('/')[-1]
            logging.info(f"删除文件: {file_path}")
            
            if self.notifier and self.notifier.notify_config.get('notify_on_delete', True):
                self.notifier.send_message(f"🗑️ 开始删除文件: {filename}")
            
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code != 200:
                error_msg = f"删除请求失败: {response.text}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                return False
            
            response_json = response.json()
            if response_json.get('code') != 200:
                error_msg = f"删除失败: {response_json.get('message')}"
                logging.error(error_msg)
                if self.notifier:
                    self.notifier.send_message(f"❌ {error_msg}", is_error=True)
                return False
            
            # 验证文件是否已被删除
            for _ in range(3):  # 最多等待15秒
                time.sleep(5)
                files = self.list_files('/'.join(file_path.split('/')[:-1]))
                if file_path.split('/')[-1] not in files:
                    success_msg = f"文件删除成功: {filename}"
                    logging.info(success_msg)
                    if self.notifier and self.notifier.notify_config.get('notify_on_delete', True):
                        self.notifier.send_message(f"✅ {success_msg}")
                    return True
            
            error_msg = f"删除超时，文件仍然存在: {filename}"
            logging.error(error_msg)
            if self.notifier:
                self.notifier.send_message(f"❌ {error_msg}", is_error=True)
            return False
            
        except Exception as e:
            error_msg = f"删除文件时发生错误: {str(e)}"
            logging.error(error_msg)
            if self.notifier:
                self.notifier.send_message(f"❌ {error_msg}", is_error=True)
            return False

def main():
    # 获取配置文件路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.json')
    
    # 加载配置
    config = load_config(config_path)
    alist_config = config['alist']
    monitor_config = config['monitor']
    notification_config = config.get('notification', {})
    
    # 创建Discord通知器
    notifier = None
    if notification_config.get('discord_webhook'):
        notifier = DiscordNotifier(
            notification_config['discord_webhook'],
            notification_config
        )
        
    # 创建Alist管理器
    try:
        # 优先使用token
        if alist_config.get('token'):
            alist = AlistFileManager(
                alist_config['url'],
                token=alist_config['token'],
                notifier=notifier
            )
        # 如果没有token，使用用户名和密码
        else:
            alist = AlistFileManager(
                alist_config['url'],
                username=alist_config.get('username'),
                password=alist_config.get('password'),
                notifier=notifier
            )
    except Exception as e:
        error_msg = f"创建Alist管理器失败: {str(e)}"
        logging.error(error_msg)
        if notifier:
            notifier.send_message(f"❌ {error_msg}", is_error=True)
        sys.exit(1)
    
    processed_files = set()
    
    startup_msg = (
        "🚀 开始监控Alist\n"
        f"源路径: {monitor_config['source_path']}\n"
        f"目标路径: {monitor_config['dest_path']}\n"
        f"检查间隔: {monitor_config['check_interval']}秒"
    )
    logging.info(startup_msg.replace('\n', ' '))
    if notifier:
        notifier.send_message(startup_msg)
    
    if monitor_config.get('delete_source', True):
        logging.info("复制后将删除源文件")
    logging.info("按Ctrl+C停止监控...")
    
    try:
        while True:
            try:
                # 获取源目录中的文件
                source_files = alist.list_files(monitor_config['source_path'])
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                logging.info(f"[{current_time}] 检查新文件...")
                
                # 处理新文件
                for filename, file_info in source_files.items():
                    if filename not in processed_files:
                        src_file_path = f"{monitor_config['source_path']}/{filename}"
                        dst_file_path = f"{monitor_config['dest_path']}/{filename}"
                        
                        file_size = file_info.get('size', 0)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        logging.info(f"发现新文件: {filename}")
                        logging.info(f"文件大小: {file_size_mb:.2f}MB")
                        
                        # 复制文件到目标目录
                        if alist.copy_file(src_file_path, dst_file_path):
                            # 复制成功后删除源文件（如果配置为True）
                            if monitor_config.get('delete_source', True):
                                if alist.delete_file(src_file_path):
                                    processed_files.add(filename)
                                    success_msg = f"文件 {filename} 已成功处理并删除源文件"
                                    logging.info(success_msg)
                                else:
                                    error_msg = f"文件 {filename} 复制成功但删除源文件失败"
                                    logging.error(error_msg)
                                    if notifier:
                                        notifier.send_message(f"⚠️ {error_msg}", is_error=True)
                            else:
                                processed_files.add(filename)
                                success_msg = f"文件 {filename} 已成功处理"
                                logging.info(success_msg)
                        else:
                            error_msg = f"文件 {filename} 处理失败"
                            logging.error(error_msg)
                            if notifier:
                                notifier.send_message(f"❌ {error_msg}", is_error=True)
                
                # 按配置的间隔时间检查
                time.sleep(monitor_config['check_interval'])
                
            except requests.exceptions.RequestException as e:
                error_msg = f"网络请求失败: {str(e)}"
                logging.error(error_msg)
                if notifier:
                    notifier.send_message(f"⚠️ {error_msg}\n等待30秒后重试...", is_error=True)
                time.sleep(30)
                continue
                
    except KeyboardInterrupt:
        print("\n")  # 为了美观，在新行显示停止消息
        stop_msg = (
            "🛑 停止监控\n"
            f"已处理的文件数量: {len(processed_files)}"
        )
        logging.info(stop_msg.replace('\n', ' '))
        
        if processed_files:
            files_msg = "已处理的文件列表:\n" + "\n".join(f"  - {filename}" for filename in sorted(processed_files))
            logging.info(files_msg)
            if notifier:
                notifier.send_message(f"{stop_msg}\n{files_msg}")
        elif notifier:
            notifier.send_message(stop_msg)
            
        sys.exit(0)
    except Exception as e:
        error_msg = f"发生错误: {str(e)}"
        logging.error(error_msg)
        if notifier:
            notifier.send_message(f"❌ {error_msg}", is_error=True)
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_msg = f"程序异常退出: {str(e)}"
        logging.error(error_msg)
        sys.exit(1)
