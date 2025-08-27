import socket

def get_rustdesk_help(server_ip, port=21114):
    """
    获取RustDesk服务器的帮助信息。
    RustDesk服务器的API端口默认是21114。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, port))
    sock.send(b"h\n")
    response = sock.recv(1024)
    sock.close()
    return response.decode()

def get_online_status(server_ip, peers, port=21116):
    """
    获取设备在线情况。
    需要安装protobuf库，并有rendezvous.proto文件。
    peers是设备ID列表。
    返回states字节，每个bit表示设备是否在线。
    """
    # 示例代码，需要protobuf
    # from rendezvous_proto import OnlineRequest, OnlineResponse
    # req = OnlineRequest()
    # req.peers = peers
    # data = req.SerializeToString()
    # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock.connect((server_ip, port))
    # sock.send(data)
    # response_data = sock.recv(1024)
    # sock.close()
    # resp = OnlineResponse()
    # resp.ParseFromString(response_data)
    # return resp.states
    pass

if __name__ == "__main__":
    server_ip = "127.0.0.1"  # 替换为你的RustDesk服务器IP
    help_text = get_rustdesk_help(server_ip)
    print("RustDesk服务器帮助信息:")
    print(help_text)
    
    # 要获取设备在线情况，取消注释并修改
    # peers = ["your_device_id"]  # 设备ID列表
    # states = get_online_status(server_ip, peers)
    # print("设备在线状态:", states)
