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

The socket object `conn` is first serialized and then sent to the child process via a `Queue`. Behind the `Queue`, there is another pair of sockets created to send and receive serialized objects. As a result, a large block of time is spent on serializing/de-serializing the objects when the volume of socket passing is high.

In a typical web server implementations, e.g. Apache and Nginx, they provide a pre-fork model instead. Workers are forked from the master process and the listen socket is inherited from the master. A mutex is applied onto the listen socket to facilicate multiprocessing. Different workers would own different set of peer sockets and thus the socket passing overhead is prevented.


Note 3 - Generating 10k simultaneous traffic on a single machine is non-trivial
--

Generating such volume of traffic can be achieved by using multi-process / multi-thread programs on a server-graded machine, but this is not the case on a consumer-graded laptop.

Multi-process is really easy in Python, you can fork multiprocesses with just a few lines of code like below.

    import multiprocessing
    
    def send_request():
        socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_.connect((HOST, PORT))
        socket_.send_all(DATA)
           :
        socket_.close()
        
    workers = multiprocessing.Pool(N)
    results = []
    for i in xrange(num_requests):
        workers.apply_async(send_request, args=(i,), callback=results.append)

Though, it is not easy to achieve 10k simultaneous traffic using this program on a customer-graded laptop. The problem is that the memory consumption is high when many processes are forked (yes, that may not be the case in C). Another problem is that having multiple CPUs do not really help this I/O bound problem where blocking I/O is used. Both problems exist in mutli-threaded program as well.

Therefore, a simple solution is to use non-blocking I/O to generate the traffic.

Of course, you can use whatever language you like to manage the 10k non-blocking sockets. In this experiment, golang was chosen instead of sticking with Python. It is because golang has a really nice co-routine scheduler (well, it's actually called go-routine and they are different). By default, golang uses non-blocking sockets and the sockets are managed by a built-in I/O event loop embedded in the scheduler. Therefore, writing such a traffic generator is as simple as below.

    func send_request() {
      addr, err := net.ResolveTCPAddr("tcp4", "127.0.0.1:8000")
      conn, err := net.DialTCP("tcp", nil, addr)
      defer conn.Close()

      _, err = conn.Write(PAYLOAD)
    }
	
	tasks := make(chan int, num_requests)
	semaphore := make(chan int, num_requests)
	
	// Create co-routines
	for i := 0; i < N; i++ {
      go func() {
        for {
          <-tasks // Block unitl task received
          send_request()
          semaphore <- 1 // Signal that the request is finished
        }
      }()
    }
    
    // Start sending requests
    for i := 0; i < num_requests; i++ {
      tasks <- 1
    }

    // Wait for all requests to be finished
    for i := 0; i < num_requests; i++ {
      <-semaphore
    }


==
