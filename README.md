Objective
--

Use different client and server implementations to try several strategies to address the c10k problem.


Details
--

A Python TCP server is implemented to echo the timestamp sent by the client. The server uses either one of the following strategies to try to handle 10K+ concurrent connections:

1. A single process to accept() connections and multiple subprocesses to echo the timestamp.
2. A single process that manages an I/O event loop implemented by select() system call. The I/O event loop accepts() connections and echos timestamp to clients upon receiving readiness notification of the underlying socket.
3. A single process that manages an I/O event loop implemented by poll() system call. The I/O event loop is similar to the one using select() system call.
4. A single process that manages an I/O event loop implemented by epoll() system call using edge-trigger. The I/O event loop is similar to the one using select() system call.


--
