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


def select_server_v0(socket_):
    '''Single process select(). Use non-blocking accept() but blocking recv().

    Since this is using single process and recv() blocks the next accept(),
    concurrency is not achieved.
    '''
    while True:
        print 'Waiting for peer'
        readable, w, e = select.select([socket_], [], [], 1)

        if socket_ not in readable:
            continue

        conn, addr = socket_.accept()
        print 'Peer connected:', addr

        handle_conn(conn, addr)


def select_server_v1(socket_):
    '''Single process select() with sub-processes to recv(). Use non-blocking
       accept() but blocking recv().

    Non-blocking accept() is not affected by the blocking recv() since the
    blocks happens in the sub-processes. Concurrency is achieved but it's only
    a slight improvement from *basic_server* because CPU time is still consumed
    for context-switching when waiting for the blocking recv().
    '''
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


def select_server_v2(socket_):
    '''Single process select() with non-blocking accept() and recv().

    When peer is accepted, use select() to see if we can recv() data from her.
    Peer is only served when she has provided data. A slow peer cannot block a
    fast peer and thus concurrency can be achieved (even though peers are
    handled one by one where sub-process can address that).
    '''
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


def epoll_server_v0(socket_):
    '''Single process epoll(). Use non-blocking accept() but blocking recv().

    Since this is using single process and recv() blocks the next accept(),
    concurrency is not achieved.
    '''
    epoll = select.epoll()
    epoll.register(socket_, select.EPOLLIN | select.EPOLLET)
    while True:
        print 'Waiting for peer'
        for fd, event in epoll.poll(timeout=1):
            if fd != socket_.fileno():
                continue

            conn, addr = socket_.accept()
            print 'Peer connected:', addr

            handle_conn(conn, addr)


def epoll_server_v1(socket_):
    '''Single process epoll() with sub-processes to recv(). Use non-blocking
       accept() but blocking recv().
    '''
    child = []
    epoll = select.epoll()
    epoll.register(socket_, select.EPOLLIN | select.EPOLLET)
    try:
        while True:
            print 'Waiting for peer'
            for fd, event in epoll.poll(timeout=1):
                if fd != socket_.fileno():
                    continue

                conn, addr = socket_.accept()
                print 'Peer connected:', addr

                p = multiprocessing.Process(target=handle_conn,
                                            args=(conn, addr))
                p.start()
                child.append(p)
    finally:
        [p.terminate() for p in child if p.is_alive()]


def epoll_server_v2(socket_):
    '''Single process select() with non-blocking accept() and recv(). '''
    epoll = select.epoll()
    epoll.register(socket_, select.EPOLLIN | select.EPOLLET)

    peers = {}  # fd => socket
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


def main():
    # Ref: http://is.gd/S1dtCH
    HOST, PORT = '127.0.0.1', 8000

    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socket_.bind((HOST, PORT))

    try:
        #socket_.listen(0)
        #basic_server(socket_)

        #socket_.setblocking(0)
        #socket_.listen(0)
        #select_server_v0(socket_)

        #socket_.setblocking(0)
        #socket_.listen(0)
        #select_server_v1(socket_)

        #socket_.setblocking(0)
        #socket_.listen(0)
        #select_server_v2(socket_)

        #socket_.setblocking(0)
        #socket_.listen(0)
        #epoll_server_v0(socket_)

        #socket_.setblocking(0)
        #socket_.listen(0)
        #epoll_server_v1(socket_)

        socket_.setblocking(0)
        socket_.listen(0)
        epoll_server_v2(socket_)
    finally:
        socket_.close()


if __name__ == '__main__':
    main()
