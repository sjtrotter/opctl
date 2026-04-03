import platform
from .infrastructure.linux import LinuxBackend
from .infrastructure.windows import WindowsBackend

def get_os_interface():
    """Factory method to return the correct OS backend."""
    current_os = platform.system()
    if current_os == "Linux":
        return LinuxBackend()
    elif current_os == "Windows":
        return WindowsBackend()
    else:
        raise NotImplementedError(f"OS {current_os} is not supported.")