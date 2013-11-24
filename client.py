import multiprocessing
import socket
import sys
import time

try:
    import argparse
except:
    # argparse is only available in Python 2.7+
    print >> sys.stderr, 'pip install -U argparse'
    sys.exit(1)


TIMEOUT = 30  # 30 seconds operation timeout


def send_request(request_id):
    HOST, PORT = '127.0.0.1', 8000
    FAILED = -1

    start = time.time()
    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_.settimeout(TIMEOUT)
    try:
        data = str(time.time())

        socket_.connect((HOST, PORT))
        socket_.sendall(data)
        reply = socket_.recv(32)

        if reply != data:
            raise Exception('data: %s, reply: %s' % (data, reply))

        finish = time.time()
        response_time = finish - start

        return response_time
    except Exception:
        return FAILED
    finally:
        socket_.close()


succeeds, total = 0, 0


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('requests', type=int,
                           help='Total number of requests')
    argparser.add_argument('--workers', type=int, default=1,
                           help=('Number of workers to generate requests in '
                                 'parallel'))
    args = argparser.parse_args()
    workers = multiprocessing.Pool(args.workers)

    def stats(response_time):
        global succeeds, total
        succeeds += 1
        total += response_time

    start = time.time()
    for i in xrange(args.requests):
        workers.apply_async(send_request, args=(i,), callback=stats)
    workers.close()
    workers.join()
    finish = time.time()

    if succeeds:
        avg = total / succeeds * 1000  # in ms.
    else:
        avg = 0
    rps = args.requests / (finish - start)
    errors = args.requests - succeeds

    msg = ('Errors: %s, Succeeds: %s\n'
           'Response time (avg.): %s ms\n'
           'Requests per second (avg.): %s req/s')
    msg = msg % (errors, succeeds, avg, rps)
    print msg


if __name__ == '__main__':
    main()
