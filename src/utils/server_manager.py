
import subprocess
import os
import json
import logging
import paramiko
import base64
import asyncio
from cryptography.fernet import Fernet
from src.utils.operation_logger import get_operation_logger

logger = logging.getLogger("ServerManager")

# Silence paramiko transport logs to keep terminal clean
logging.getLogger("paramiko").setLevel(logging.WARNING)


async def _send_whapi_notification(operation: str, status: str, output: str):
    """Send operation notification via Whapi (async)"""
    try:
        from src.utils.notification_service import get_notification_service
        notif = get_notification_service()
        status_emoji = "✅" if status == "success" else "❌"
        message = f"{status_emoji} *{operation.upper()}*\nStatus: {status}\n\n{output[:150]}"
        await notif.send_alert(message, channels=["whapi"])
    except Exception as e:
        logger.debug(f"Whapi notification skipped: {e}")


def _notify_async(coro):
    """Execute async notification without blocking"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except Exception as e:
        logger.debug(f"Async notification error: {e}")


# Encryption key - derived from environment or machine ID
def _get_encryption_key():
    """Get or create encryption key for SSH credentials"""
    key_file = os.path.join(os.path.expanduser("~"), ".mavi_lojistik_ssh_key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        with open(key_file, "wb") as f:
            f.write(key)
        os.chmod(key_file, 0o600)  # Restrict permissions
        return key

_ENCRYPTION_KEY = _get_encryption_key()

class ServerManager:
    """
    Purpose:      Manages PM2 processes and server operations (Local or SSH)
    Inputs:       service_name (str), ssh_config (dict)
    Outputs:      Command results as strings or JSON
    Dependencies: subprocess, paramiko, pm2
    Usage:        Used by GUI for remote/local management
    """
    def __init__(self, service_name="mavi-lojistik-server", ssh_config=None):
        self.service_name = service_name
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.ssh_config = ssh_config or self._load_ssh_config() # Otomatik yükle

    def _load_ssh_config(self):
        """Loads and decrypts SSH config from data/ssh_config.json if exists"""
        config_path = os.path.join(self.root_dir, "data", "ssh_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Decrypt password if encrypted
                if data.get('pwd') and data.get('pwd').startswith('encrypted:'):
                    try:
                        cipher = Fernet(_ENCRYPTION_KEY)
                        encrypted_pwd = data['pwd'].replace('encrypted:', '')
                        data['pwd'] = cipher.decrypt(encrypted_pwd.encode()).decode()
                    except Exception as e:
                        logger.warning(f"Password decryption failed: {e}")
                        del data['pwd']  # Remove invalid password

                return data
            except Exception as e:
                logger.error(f"SSH config load error: {e}")
        return None

    def save_ssh_config(self, config):
        """Saves SSH config with encrypted password"""
        config = config.copy()  # Don't modify original
        if config.get('pwd'):
            cipher = Fernet(_ENCRYPTION_KEY)
            encrypted = cipher.encrypt(config['pwd'].encode()).decode()
            config['pwd'] = f"encrypted:{encrypted}"

        config_path = os.path.join(self.root_dir, "data", "ssh_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("SSH config saved (password encrypted)")

    def _execute(self, cmd_list):
        if self.ssh_config and self.ssh_config.get('host'):
            return self._execute_ssh(" ".join(cmd_list))
        
        try:
            # Use shell=True for PM2 to work correctly across different environments
            process = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=15,
                shell=True,
                cwd=self.root_dir
            )
            if process.returncode == 0:
                return True, process.stdout
            else:
                return False, process.stderr or process.stdout
        except FileNotFoundError:
            return False, f"Hata: '{cmd_list[0]}' komutu bu sistemde yüklü değil."
        except subprocess.TimeoutExpired:
            return False, "Hata: Komut zaman aşımına uğradı."
        except Exception as e:
            return False, f"Hata: {str(e)}"

    def _execute_ssh(self, command):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Otonom bağlantı denemesi
            host = self.ssh_config.get('host')
            user = self.ssh_config.get('user', 'root')
            pwd = self.ssh_config.get('pwd')
            port = int(self.ssh_config.get('port', 22))

            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": user,
                "timeout": 10,
                "look_for_keys": True,
                "allow_agent": True
            }
            if pwd: connect_kwargs["password"] = pwd
            ssh.connect(**connect_kwargs)
            
            # Önce klasörün varlığını kontrol et
            check_cmd = "test -d ~/mavi-lojistik-otomasyon && echo 'exists' || echo 'missing'"
            _, stdout_c, _ = ssh.exec_command(check_cmd)
            if stdout_c.read().decode().strip() == 'missing':
                ssh.close()
                return False, "Hata: Sunucuda '~/mavi-lojistik-otomasyon' klasörü bulunamadı."

            # Execute command in project directory
            full_command = f"cd ~/mavi-lojistik-otomasyon && {command}"
            stdin, stdout, stderr = ssh.exec_command(full_command)
            out = stdout.read().decode('utf-8')
            err = stderr.read().decode('utf-8')
            ssh.close()
            
            # PM2 jlist might output to stdout even if successful
            if "pm2" in command and "jlist" in command:
                return True, out
                
            if err and "error" in err.lower():
                return False, err
            return True, out or err
        except Exception as e:
            return False, f"SSH Hatası: {str(e)}"

    def get_status_summary(self):
        """Returns complete status including process, disk, and system metrics"""
        status_data = self._get_pm2_status()

        # Add disk metrics
        status_data["disk"] = self._get_disk_usage()

        # Add system metrics (via df and free commands)
        status_data["system"] = self._get_system_metrics()

        return status_data

    def _get_pm2_status(self):
        """Get PM2 process status"""
        success, output = self._execute(["pm2", "jlist"])
        if success and output and output.strip():
            try:
                # Clean output for potential SSH banner messages
                if "[" in output:
                    output = output[output.find("["):]

                if output.startswith("["):
                    data = json.loads(output)
                    for app in data:
                        if app.get('name') == self.service_name:
                            pm2_env = app.get('pm2_env', {})
                            return {
                                "status": pm2_env.get('status', 'unknown'),
                                "cpu": app.get('monit', {}).get('cpu', 0),
                                "memory": app.get('monit', {}).get('memory', 0) / (1024*1024),
                                "uptime": pm2_env.get('pm_uptime', 0),
                                "restarts": pm2_env.get('restart_time', 0)
                            }
            except Exception as e:
                logger.error(f"Status parse error: {e}")

        # Eğer klasör hatası veya başka bir hata mesajı gelmişse, durumu o mesajla güncelle
        return {"status": output if not success else "offline", "cpu": 0, "memory": 0, "uptime": 0, "restarts": 0}

    def _get_disk_usage(self):
        """Get disk usage percentage"""
        try:
            if self.ssh_config and self.ssh_config.get('host'):
                success, output = self._execute_ssh("df -h / | tail -1 | awk '{print $5}'")
            else:
                success, output = self._execute(["df", "-h", "/"])

            if success and output:
                if self.ssh_config:
                    # SSH output is just the percentage
                    return int(output.strip().replace('%', ''))
                else:
                    # Parse df output for root filesystem
                    lines = output.split('\n')
                    if len(lines) > 1:
                        percent_str = lines[1].split()[4].replace('%', '')
                        return int(percent_str)

            return 0
        except Exception as e:
            logger.debug(f"Disk usage error: {e}")
            return 0

    def _get_system_metrics(self):
        """Get system-wide metrics (memory, load average)"""
        metrics = {}

        try:
            if self.ssh_config and self.ssh_config.get('host'):
                # Memory usage
                success, output = self._execute_ssh("free | grep Mem | awk '{print ($3/$2) * 100}'")
                if success:
                    metrics['memory_percent'] = float(output.strip())

                # Load average
                success, output = self._execute_ssh("cat /proc/loadavg | awk '{print $1, $2, $3}'")
                if success:
                    loads = output.strip().split()
                    metrics['load_average'] = {"1min": float(loads[0]), "5min": float(loads[1]), "15min": float(loads[2])}
            else:
                # Local system metrics using psutil if available
                try:
                    import psutil
                    metrics['memory_percent'] = psutil.virtual_memory().percent
                    metrics['load_average'] = {
                        "1min": os.getloadavg()[0],
                        "5min": os.getloadavg()[1],
                        "15min": os.getloadavg()[2]
                    }
                except:
                    pass

        except Exception as e:
            logger.debug(f"System metrics error: {e}")

        return metrics

    def restart(self):
        success, output = self._execute(["pm2", "restart", self.service_name])
        status = "success" if success else "failure"
        get_operation_logger().log_operation(
            "restart",
            status,
            {"output": output[:200], "service": self.service_name}
        )
        _notify_async(_send_whapi_notification("restart", status, output[:200]))
        return success, output

    def stop(self):
        success, output = self._execute(["pm2", "stop", self.service_name])
        status = "success" if success else "failure"
        get_operation_logger().log_operation(
            "stop",
            status,
            {"output": output[:200], "service": self.service_name}
        )
        _notify_async(_send_whapi_notification("stop", status, output[:200]))
        return success, output

    def start(self):
        success, output = self._execute(["pm2", "start", "ecosystem.config.js", "--only", self.service_name])
        status = "success" if success else "failure"
        get_operation_logger().log_operation(
            "start",
            status,
            {"output": output[:200], "service": self.service_name}
        )
        _notify_async(_send_whapi_notification("start", status, output[:200]))
        return success, output

    def get_logs(self, lines=50):
        """Reads log files from local or remote"""
        if self.ssh_config and self.ssh_config.get('host'):
            # Dinamik olarak log yolunu PM2'den öğrenmeye çalış, bulamazsa standart yolları dene
            get_path_cmd = f"pm2 show {self.service_name} | grep 'out log path' | sed 's/│//g' | awk '{{print $4}}'"
            cmd = f"LOG_PATH=$({get_path_cmd}); [ -n \"$LOG_PATH\" ] && [ -f \"$LOG_PATH\" ] && tail -n {lines} \"$LOG_PATH\" || (tail -n {lines} logs/pm2_out.log 2>/dev/null || tail -n {lines} ~/.pm2/logs/{self.service_name}-out.log 2>/dev/null)"
            
            success, output = self._execute_ssh(cmd)
            # Eğer çıktı tamamen boşsa bilgi ver
            if not output or output.strip() == "":
                output = "Sunucuda henüz log kaydı oluşmadı veya servis çıktı üretmiyor."
            return output if success else f"Log çekilemedi: {output}"

        log_paths = [
            os.path.join(self.root_dir, "logs", "pm2_out.log"),
            os.path.join(self.root_dir, "logs", "vps_runtime.log")
        ]
        
        combined_logs = []
        for path in log_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.readlines()
                        combined_logs.append(f"--- {os.path.basename(path)} ---")
                        combined_logs.extend(content[-lines:])
                except Exception as e:
                    combined_logs.append(f"Error reading {path}: {e}")
        
        return "\n".join(combined_logs) if combined_logs else "Log bulunamadı."

    def git_pull(self):
        """Safe git pull with backup and rollback capability"""
        from src.utils.deployment_manager import get_deployment_manager

        deployment_mgr = get_deployment_manager(self.root_dir)

        # Step 1: Create backup
        backup_ok, backup_path = deployment_mgr.create_backup()
        if not backup_ok:
            logger.error(f"Backup creation failed: {backup_path}")
            return False, f"Backup failed: {backup_path}"

        # Step 2: Perform git pull
        success, output = self._execute(["git", "pull"])

        if not success:
            # Rollback on failure
            logger.warning("Git pull failed, attempting rollback...")
            rollback_ok, rollback_msg = deployment_mgr.rollback(backup_path)
            error_msg = f"Git pull failed. Rollback: {'Success' if rollback_ok else rollback_msg}"
            get_operation_logger().log_operation(
                "git_pull",
                "failure_with_rollback",
                {"error": output[:200], "rollback": rollback_msg[:200]}
            )
            _notify_async(_send_whapi_notification("git_pull", "FAILURE - Rolled Back", error_msg))
            return False, error_msg

        # Step 3: Log and notify success
        get_operation_logger().log_operation(
            "git_pull",
            "success",
            {"output": output[:200], "backup": os.path.basename(backup_path)}
        )
        _notify_async(_send_whapi_notification("git_pull", "success", output[:200]))

        # Cleanup old backups
        deployment_mgr.cleanup_old_backups()

        return True, output
