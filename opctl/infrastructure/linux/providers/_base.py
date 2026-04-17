import subprocess
from typing import List


class LinuxProvider:
    def _run(self, cmd: List[str]) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"Command error: {error_msg}\nCommand: {' '.join(cmd)}")
