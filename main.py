import multiprocessing
import os
import socket


def handle_conn(conn, addr):
    msg = 'Process: %(pid)s; Client: %(addr)s' % {
        'pid': os.getpid(),
        'addr': addr,
    }
    print msg

    data = conn.recv(32)
    conn.sendall(data)
    conn.close()


def basic_server(socket_):
    child = []
    try:
        while True:
            conn, addr = socket_.accept()
            p = multiprocessing.Process(target=handle_conn, args=(conn, addr))
            p.start()
            child.append(p)
    except:
        pass
    finally:
        [p.terminate() for p in child if p.is_alive()]


def main():
    # Ref: http://is.gd/S1dtCH
    HOST, PORT = '127.0.0.1', 8000

    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_.bind((HOST, PORT))

    try:
        socket_.listen(0)
        basic_server(socket_)
    finally:
        socket_.close()


if __name__ == '__main__':
    main()
