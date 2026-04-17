import platform
from opctl.domain.models.backend import BackendConfig


def get_os_interface(config: BackendConfig = None):
    """Factory: return the OS backend coordinator with detected or configured providers."""
    current_os = platform.system()
    if current_os == "Linux":
        from .infrastructure.linux.backend import LinuxBackend
        return LinuxBackend(config)
    elif current_os == "Windows":
        from .infrastructure.windows.backend import WindowsBackend
        return WindowsBackend(config)
    else:
        raise NotImplementedError(f"OS '{current_os}' is not supported.")
