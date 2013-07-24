import socket


def main():
    # Ref: http://is.gd/S1dtCH
    HOST, PORT = '127.0.0.1', 8000

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))

    s.listen(0)

    conn, addr = s.accept()
    print 'Connected: %(addr)s' % {'addr': addr}
    while True:
        data = conn.recv(1024)
        if not data:
            break

        conn.sendall(data)
        conn.close()


if __name__ == '__main__':
    main()
