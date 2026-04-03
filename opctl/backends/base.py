from abc import ABC, abstractmethod

class NetworkBackend(ABC):
    """
    Abstract Base Class defining the required interface for all OS backends.
    Any new OS support must implement these methods.
    """

    @abstractmethod
    def get_hostname(self):
        pass

    @abstractmethod
    def set_hostname(self, hostname):
        pass

    @abstractmethod
    def get_hwaddress(self, iface):
        pass

    @abstractmethod
    def set_fw_rule(self, ip_address, action="allow"):
        pass