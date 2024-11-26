# jsockets para Python3
# sería bonito tener soporte para multicast
import socket
import sys

# accept no aporta nada en realidad...
def accept(s):
    return s.accept()

def socket_tcp_bind(port):
    return socket_bind(socket.SOCK_STREAM, port)

def socket_udp_bind(port):
    return socket_bind(socket.SOCK_DGRAM, port)

def socket_bind(type, port):
    s = None
    for res in socket.getaddrinfo(None, port, socket.AF_UNSPEC, type, 0, socket.AI_PASSIVE):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error as msg:
            s = None
            continue
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if(type == socket.SOCK_DGRAM):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                # s.setsockopt(socket.IPPROTO_IP, socket.IP_MTU_DISCOVER, 0) Para Linux?
            s.bind(sa)
            if(type == socket.SOCK_STREAM):
                s.listen(5)
        except socket.error as msg:
            s.close()
            s = None
            print(msg)
            break
        break

    return s

def socket_tcp_connect(server, port):
    return socket_connect(socket.SOCK_STREAM, server, port)

def socket_udp_connect(server, port):
    return socket_connect(socket.SOCK_DGRAM, server, port)

#def socket_udp_unconnect(s):
#    return s.connect((0, 0)) # no funciona con '' ni None ni 0

def socket_connect(type, server, port):
    s = None
    for res in socket.getaddrinfo(server, port, socket.AF_UNSPEC, type):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error as msg:
            s = None
            continue
        try:
            s.connect(sa)
        except socket.error as msg:
            s.close()
            s = None
            continue
        break

    return s
