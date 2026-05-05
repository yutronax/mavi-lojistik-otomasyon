
import subprocess
import os
import json
import logging
import paramiko

logger = logging.getLogger("ServerManager")

# Silence paramiko transport logs to keep terminal clean
logging.getLogger("paramiko").setLevel(logging.WARNING)

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
        """Loads SSH config from data/ssh_config.json if exists"""
        config_path = os.path.join(self.root_dir, "data", "ssh_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"SSH config load error: {e}")
        return None

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
        """Returns a simplified status of the process"""
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

    def restart(self):
        return self._execute(["pm2", "restart", self.service_name])

    def stop(self):
        return self._execute(["pm2", "stop", self.service_name])

    def start(self):
        return self._execute(["pm2", "start", "ecosystem.config.js", "--only", self.service_name])

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
        return self._execute(["git", "pull"])
