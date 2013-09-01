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
    except Exception as e:
        return FAILED
    finally:
        socket_.close()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('requests', type=int,
                           help='Total number of requests')
    argparser.add_argument('--workers', type=int, default=1,
                           help=('Number of workers to generate requests in '
                                 'parallel'))
    args = argparser.parse_args()

    workers = multiprocessing.Pool(args.workers)
    async_results = [workers.apply_async(send_request, args=(i,))
                     for i in xrange(args.requests)]
    workers.close()

    errors, succeeds, total = 0, 0, 0
    for async_result in async_results:
        try:
            response_time = async_result.get(timeout=TIMEOUT)
        except Exception as e:
            response_time = -1

        if response_time == -1:
            errors += 1
        else:
            succeeds += 1
            total += response_time

    workers.join()
    if succeeds:
        avg = total / succeeds * 1000
    else:
        avg = 0

    msg = 'Errors: %s, Succeeds: %s, Avg. Response Time: %s ms'
    msg = msg % (errors, succeeds, avg)
    print msg


if __name__ == '__main__':
    main()
