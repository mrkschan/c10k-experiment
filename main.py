import multiprocessing
import os
import select
import socket


def handle_conn(conn, addr):
    msg = 'Process: %(pid)s; Peer: %(addr)s' % {
        'pid': os.getpid(),
        'addr': addr,
    }
    print msg

    data = conn.recv(32)
    conn.sendall(data)
    conn.close()


def select_server(socket_):
    child = []
    try:
        while True:
            print 'Waiting for peer'
            readable, w, e = select.select([socket_], [], [], 1)

            if socket_ not in readable:
                continue

            conn, addr = socket_.accept()
            print 'Peer connected:', addr

            p = multiprocessing.Process(target=handle_conn, args=(conn, addr))
            p.start()
            child.append(p)
    finally:
        [p.terminate() for p in child if p.is_alive()]


def basic_server(socket_):
    child = []
    try:
        while True:
            print 'Waiting for peer'

            conn, addr = socket_.accept()
            print 'Peer connected:', addr

            p = multiprocessing.Process(target=handle_conn, args=(conn, addr))
            p.start()
            child.append(p)
    finally:
        [p.terminate() for p in child if p.is_alive()]


def main():
    # Ref: http://is.gd/S1dtCH
    HOST, PORT = '127.0.0.1', 8000

    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socket_.bind((HOST, PORT))

    try:
        #socket_.listen(0)
        #basic_server(socket_)

        socket_.setblocking(0)
        socket_.listen(0)
        select_server(socket_)
    finally:
        socket_.close()


if __name__ == '__main__':
    main()
