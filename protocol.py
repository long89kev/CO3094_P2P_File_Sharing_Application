class Protocol:    
    # Client-Server Protocol Messages
    REGISTER = "REGISTER"
    REGISTER_SUCCESS = "REGISTER_SUCCESS"
    REGISTER_FAIL = "REGISTER_FAIL"
    
    PUBLISH = "PUBLISH"
    PUBLISH_SUCCESS = "PUBLISH_SUCCESS"
    PUBLISH_FAIL = "PUBLISH_FAIL"
    
    FETCH = "FETCH"
    FETCH_OK = "FETCH_OK"
    FETCH_NOT_FOUND = "FETCH_NOT_FOUND"
    
    LIST_CLIENTS = "LIST_CLIENTS"
    LIST_CLIENTS_OK = "LIST_CLIENTS_OK"
    
    DISCOVER_CLIENT = "DISCOVER_CLIENT"
    DISCOVER_CLIENT_OK = "DISCOVER_CLIENT_OK"
    DISCOVER_CLIENT_NOT_FOUND = "DISCOVER_CLIENT_NOT_FOUND"
    
    # Peer-to-Peer Protocol Messages
    DOWNLOAD = "DOWNLOAD"
    FILESIZE = "FILESIZE"
    BEGIN_DOWNLOAD = "BEGIN_DOWNLOAD"
    ERROR = "ERROR"
    
    # Server Commands
    DISCOVER = "DISCOVER"
    PING = "PING"
    LIST = "LIST"
    FILES = "FILES"
    QUIT = "QUIT"


class ProtocolHelper:    
    @staticmethod
    def create_register_message(hostname, p2p_port):
        return f"{Protocol.REGISTER} {hostname} {p2p_port}"
    
    @staticmethod
    def create_publish_message(filename, hostname):
        return f"{Protocol.PUBLISH} {filename} {hostname}"
    
    @staticmethod
    def create_fetch_message(filename):
        return f"{Protocol.FETCH} {filename}"
    
    @staticmethod
    def create_list_clients_message():
        return f"{Protocol.LIST_CLIENTS}"
    
    @staticmethod
    def create_discover_client_message(hostname):
        return f"{Protocol.DISCOVER_CLIENT} {hostname}"
    
    @staticmethod
    def create_download_message(filename):
        return f"{Protocol.DOWNLOAD} {filename}"
    
    @staticmethod
    def create_filesize_message(size):
        return f"{Protocol.FILESIZE} {size}"
    
    @staticmethod
    def parse_message(message):
        parts = message.strip().split()
        if not parts:
            return None, []
        return parts[0], parts[1:]
    
    @staticmethod
    def parse_peer_list(peer_list_str):
        peers = []
        parts = peer_list_str.split()
        
        for peer_info in parts:
            peer_parts = peer_info.split(':')
            if len(peer_parts) >= 3:
                peers.append({
                    'ip': peer_parts[0],
                    'port': int(peer_parts[1]),
                    'hostname': peer_parts[2]
                })
        
        return peers
