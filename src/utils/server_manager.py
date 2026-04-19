
import subprocess
import os
import json
import logging

logger = logging.getLogger("ServerManager")

class ServerManager:
    """
    Purpose:      Manages PM2 processes and server operations
    Inputs:       service_name (str): Name of the PM2 process
    Outputs:      Command results as strings or JSON
    Dependencies: subprocess, pm2
    Usage:        Used by ServerControlPage for remote/mobile management
    """
    def __init__(self, service_name="mavi-lojistik-server"):
        self.service_name = service_name
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _execute(self, cmd_list):
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
        except subprocess.TimeoutExpired:
            return False, "Hata: Komut zaman aşımına uğradı."
        except Exception as e:
            return False, f"Hata: {str(e)}"

    def get_status_summary(self):
        """Returns a simplified status of the process"""
        success, output = self._execute(["pm2", "jlist"])
        if success:
            try:
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
            except:
                pass
        return {"status": "offline", "cpu": 0, "memory": 0, "uptime": 0, "restarts": 0}

    def restart(self):
        return self._execute(["pm2", "restart", self.service_name])

    def stop(self):
        return self._execute(["pm2", "stop", self.service_name])

    def start(self):
        # Assumes ecosystem.config.js is in root
        return self._execute(["pm2", "start", "ecosystem.config.js", "--only", self.service_name])

    def get_logs(self, lines=50):
        """Reads log files directly for efficiency"""
        log_paths = [
            os.path.join(self.root_dir, "logs", "pm2_out.log"),
            os.path.join(self.root_dir, "logs", "vps_runtime.log")
        ]
        
        combined_logs = []
        for path in log_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        # Optimization: seek to end and read last lines if needed
                        # For now, simple readlines is okay for 50 lines
                        content = f.readlines()
                        combined_logs.append(f"--- {os.path.basename(path)} ---")
                        combined_logs.extend(content[-lines:])
                except Exception as e:
                    combined_logs.append(f"Error reading {path}: {e}")
        
        return "\n".join(combined_logs) if combined_logs else "Log bulunamadı."

    def git_pull(self):
        """Simple git pull to update the server code"""
        return self._execute(["git", "pull"])
