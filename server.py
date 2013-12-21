from multiprocessing.reduction import reduce_socket
import multiprocessing
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
    data = conn.recv(32)
    conn.sendall(data)
    conn.close()


def queued_handle_conn(queue):
    while True:
        rebuild_func, hints, addr = queue.get()
        conn = rebuild_func(*hints)
        handle_conn(conn, addr)


def basic_server(socket_):
    child = []
    try:
        while True:
            conn, addr = socket_.accept()

            p = multiprocessing.Process(target=handle_conn, args=(conn, addr))
            p.start()
            child.append(p)
    finally:
        [p.terminate() for p in child if p.is_alive()]


def select_server(socket_, timeout=1, use_worker=False):
    '''Single process select() with non-blocking accept() and recv().'''
    peers = []

    try:
        max_peers = 0

        if use_worker:
            queue = multiprocessing.Queue()
            worker = multiprocessing.Process(target=queued_handle_conn,
                                             args=(queue,))
            worker.start()

        while True:
            max_peers = max(max_peers, len(peers))
            readable, w, e = select.select(peers + [socket_], [], [], timeout)

            for s in readable:
                if s is socket_:
                    while True:
                        try:
                            conn, addr = socket_.accept()
                            conn.setblocking(0)

                            peers.append(conn)
                        except:
                            break
                else:
                    peers.remove(s)
                    conn, addr = s, s.getpeername()

                    if use_worker:
                        # Behind-the-scene: 'conn' is serialized and sent to
                        # worker process via socket (IPC).
                        rebuild_func, hints = reduce_socket(conn)
                        queue.put((rebuild_func, hints, addr))
                    else:
                        handle_conn(conn, addr)
    finally:
        if use_worker and worker.is_alive():
            worker.terminate()

        print 'Max. number of connections:', max_peers


def poll_server(socket_, timeout=1, use_worker=False):
    '''Single process poll() with non-blocking accept() and recv().'''
    peers = {}  # {fileno: socket}
    flag = (select.POLLIN |
            select.POLLERR |
            select.POLLHUP)

    try:
        max_peers = 0

        if use_worker:
            queue = multiprocessing.Queue()
            worker = multiprocessing.Process(target=queued_handle_conn,
                                             args=(queue,))
            worker.start()

        poll = select.poll()
        poll.register(socket_, select.POLLIN)
        while True:
            max_peers = max(max_peers, len(peers))
            actionable = poll.poll(timeout)

            for fd, event in actionable:
                if fd == socket_.fileno():
                    while True:
                        try:
                            conn, addr = socket_.accept()
                            conn.setblocking(0)

                            peers[conn.fileno()] = conn
                            poll.register(conn, flag)
                        except:
                            break

                elif event & select.POLLIN:
                    poll.unregister(fd)
                    conn, addr = peers[fd], peers[fd].getpeername()

                    if use_worker:
                        # Behind-the-scene: 'conn' is serialized and sent to
                        # worker process via socket (IPC).
                        rebuild_func, hints = reduce_socket(conn)
                        queue.put((rebuild_func, hints, addr))
                    else:
                        handle_conn(conn, addr)

                elif event & select.POLLERR or event & select.POLLHUP:
                    poll.unregister(fd)
                    peers[fd].close()
    finally:
        if use_worker and worker.is_alive():
            worker.terminate()

        print 'Max. number of connections:', max_peers


def epoll_server(socket_, timeout=1, use_worker=False):
    '''Single process epoll() with non-blocking accept() and recv().'''
    peers = {}  # {fileno: socket}
    flag = (select.EPOLLIN |
            select.EPOLLET |
            select.EPOLLERR |
            select.EPOLLHUP)

    try:
        max_peers = 0

        if use_worker:
            queue = multiprocessing.Queue()
            worker = multiprocessing.Process(target=queued_handle_conn,
                                             args=(queue,))
            worker.start()

        epoll = select.epoll()
        epoll.register(socket_, select.EPOLLIN | select.EPOLLET)
        while True:
            max_peers = max(max_peers, len(peers))
            actionable = epoll.poll(timeout=timeout)

            for fd, event in actionable:
                if fd == socket_.fileno():
                    while True:
                        try:
                            conn, addr = socket_.accept()
                            conn.setblocking(0)

                            peers[conn.fileno()] = conn
                            epoll.register(conn, flag)
                        except:
                            break

                elif event & select.EPOLLIN:
                    epoll.unregister(fd)
                    conn, addr = peers[fd], peers[fd].getpeername()

                    if use_worker:
                        # Behind-the-scene: 'conn' is serialized and sent to
                        # worker process via socket (IPC).
                        rebuild_func, hints = reduce_socket(conn)
                        queue.put((rebuild_func, hints, addr))
                    else:
                        handle_conn(conn, addr)

                elif event & select.EPOLLERR or event & select.EPOLLHUP:
                    epoll.unregister(fd)
                    peers[fd].close()
    finally:
        if use_worker and worker.is_alive():
            worker.terminate()
        epoll.close()

        print 'Max. number of connections:', max_peers


def main():
    HOST, PORT = '127.0.0.1', 8000
    MODES = ('basic', 'select', 'poll', 'epoll')

    argparser = argparse.ArgumentParser()
    argparser.add_argument('mode', help=('Operating mode of the server: %s'
                                         % ', '.join(MODES)))
    argparser.add_argument('--backlog', type=int, default=0,
                           help='socket.listen() backlog')
    argparser.add_argument('--timeout', type=int, default=1000,
                           help='select/poll/epoll timeout in ms')
    argparser.add_argument('--worker', action='store_true',
                           help=('Spawn a worker to process request in '
                                 'select/poll/epoll mode. '
                                 'NOTE: The sole purpose of this option is '
                                 'experiment, it does not really help shorten '
                                 'the response time.'))
    args = argparser.parse_args()

    if args.mode not in MODES:
        msg = 'Availble operating modes: %s' % ', '.join(MODES)
        print >> sys.stderr, msg
        sys.exit(1)

    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        socket_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_.bind((HOST, PORT))

        if args.mode in ('select', 'poll', 'epoll'):
            socket_.setblocking(0)

        timeout = args.timeout / 1000
        socket_.listen(args.backlog)
        if args.mode == 'basic':
            basic_server(socket_)
        elif args.mode == 'select':
            select_server(socket_, timeout, use_worker=args.worker)
        elif args.mode == 'poll':
            poll_server(socket_, timeout, use_worker=args.worker)
        elif args.mode == 'epoll':
            epoll_server(socket_, timeout, use_worker=args.worker)
    except KeyboardInterrupt:
        pass
    finally:
        socket_.close()


if __name__ == '__main__':
    main()
