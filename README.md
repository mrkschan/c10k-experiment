Objective
==

Use different client and server implementations to try several strategies to address the c10k problem.


Details
==

A Python TCP server is implemented to echo the timestamp sent by the client. The server uses either one of the following strategies to try to handle 10K+ concurrent connections:

1. A single process to accept() connections and multiple subprocesses to echo the timestamp.
2. A single process that manages an I/O event loop implemented by select() system call. The I/O event loop accepts() connections and echos timestamp to clients upon receiving readiness notification of the underlying socket.
3. A single process that manages an I/O event loop implemented by poll() system call. The I/O event loop is similar to the one using select() system call.
4. A single process that manages an I/O event loop implemented by epoll() system call using edge-trigger. The I/O event loop is similar to the one using select() system call.


Note 1 - Number of pending connections is unknown
--

No matter which of the readiness model is used, the queue length of `socket.accept()` is unknown. According to the man page of `accept()`:

> If no pending connections are present on the queue, and the socket is not marked as nonblocking, accept() blocks the caller until a connection is present. If the socket is marked nonblocking and no pending connections are present on the queue, accept() fails with the error EAGAIN or EWOULDBLOCK.

Therefore, when the server socket is ready to accept a connection, the entire connection queue must be consumed like below.

    peers = {}
    for sock in actionable:
      if sock == server_sock:
        while True:
          try:
            conn, addr = socket_.accept()
            conn.setblocking(0)

            peers[conn.fileno()] = conn
          except:
            break
      else:
        # Handle peer read/write

If the entire connection queue is not consumed, the queue will keep growing until hitting the queue size defined by the `backlog` parameter of `listen()`. The system then rejects any new connection / TCP handshake.


Note 2 - High volume socket passing between Python subprocesses should be prevented
--

In Python, you can pass around a socket object easily with the multiprocessing module like below.

    from multiprocessing.reduction import reduce_socket
    import multiprocessing

    def parent():
        queue = multiprocessing.Queue()
        my_child = multiprocessing.Process(target=child, args=(queue,))
        my_child.start()

        conn = socket.accept()
        rebuild_func, hints = reduce_socket(conn)  # Serialize conn
        queue.put((rebuild_func, hints))  # Pass to my_child
            :
            :

    def child(queue):
        rebuild_func, hints = queue.get()
        conn = rebuild_func(*hints)  # De-serialize conn
            :
            :

The socket object `conn` is first serialized and then sent to the child process via a `Queue`. Behind the `Queue`, there is another pair of sockets created to send and receive serialized objects. As a result, a large block of time is spent on serializing/de-serializing the objects when the volume of socket passing is high. (TODO: Can we send fd without using socket?)

==
