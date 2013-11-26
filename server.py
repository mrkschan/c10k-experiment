import multiprocessing
import os
import select
import socket
import sys

try:
    import argparse
except:
    # argparse is only available in Python 2.7+
    print >> sys.stderr, 'pip install -U argparse'
    sys.exit(1)


def handle_conn(conn, addr):
    msg = 'Process: %(pid)s; Peer: %(addr)s' % {
        'pid': os.getpid(),
        'addr': addr,
    }
    print msg

    print 'Wait for data from peer'
    data = conn.recv(32)

    print 'Data received from peer'
    conn.sendall(data)
    conn.close()


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


def select_server(socket_):
    '''Single process select() with non-blocking accept() and recv().'''
    socks = [socket_]
    while True:
        print 'Waiting for peer'
        readable, w, e = select.select(socks, [], [], 1)

        for s in readable:
            if s is socket_:
                conn, addr = socket_.accept()
                conn.setblocking(0)

                print 'Peer connected:', addr
                socks.append(conn)
            else:
                socks.remove(s)
                conn, addr = s, s.getpeername()

                print 'Peer ready:', addr
                handle_conn(conn, addr)


def epoll_server(socket_):
    '''Single process select() with non-blocking accept() and recv().'''
    peers = {}  # fd => socket

    try:
        epoll = select.epoll()
        epoll.register(socket_, select.EPOLLIN | select.EPOLLET)
        while True:
            print 'Waiting for peer'
            for fd, event in epoll.poll(timeout=1):
                if fd == socket_.fileno():
                    conn, addr = socket_.accept()
                    conn.setblocking(0)

                    print 'Peer connected:', addr

                    peers[conn.fileno()] = conn
                    epoll.register(conn, select.EPOLLIN | select.EPOLLET)

                elif event & select.EPOLLIN:
                    epoll.unregister(fd)

                    conn, addr = peers[fd], peers[fd].getpeername()

                    print 'Peer ready:', addr
                    handle_conn(conn, addr)
    finally:
        epoll.close()


def main():
    HOST, PORT = '127.0.0.1', 8000
    MODES = ('basic', 'select', 'epoll')

    argparser = argparse.ArgumentParser()
    argparser.add_argument('mode', help=('Operating mode of the server: %s'
                                         % ', '.join(MODES)))
    argparser.add_argument('--backlog', type=int, default=0,
                           help='socket.listen() backlog')
    args = argparser.parse_args()

    if args.mode not in MODES:
        msg = 'Availble operating modes: %s' % ', '.join(MODES)
        print >> sys.stderr, msg
        sys.exit(1)

    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        socket_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_.bind((HOST, PORT))

        if args.mode in ('select', 'epoll'):
            socket_.setblocking(0)

        socket_.listen(args.backlog)
        if args.mode == 'basic':
            basic_server(socket_)
        elif args.mode == 'select':
            select_server(socket_)
        elif args.mode == 'epoll':
            epoll_server(socket_)
    except KeyboardInterrupt:
        pass
    finally:
        socket_.close()


if __name__ == '__main__':
    main()
