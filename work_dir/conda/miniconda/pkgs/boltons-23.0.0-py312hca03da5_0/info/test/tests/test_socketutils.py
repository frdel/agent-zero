# -*- coding: utf-8 -*-

import sys
import time
import errno
import socket
import threading
from boltons.socketutils import (BufferedSocket,
                                 NetstringSocket,
                                 ConnectionClosed,
                                 NetstringMessageTooLong,
                                 MessageTooLong,
                                 Timeout)

import pytest

# skip if there's no socketpair
pytestmark = pytest.mark.skipif(getattr(socket, 'socketpair', None) is None,
                                reason='no socketpair (likely Py2 on Windows)')


def test_short_lines():
    for ms in (2, 4, 6, 1024, None):
        x, y = socket.socketpair()
        bs = BufferedSocket(x)
        y.sendall(b'1\n2\n3\n')
        assert bs.recv_until(b'\n', maxsize=ms) == b'1'
        assert bs.recv_until(b'\n', maxsize=ms) == b'2'
        y.close()
        assert bs.recv_close(maxsize=ms) == b'3\n'

        try:
            bs.recv_size(1)
        except ConnectionClosed:
            pass
        else:
            assert False, 'expected ConnectionClosed'

        bs.close()
    return


def test_multibyte_delim():
    """Primarily tests recv_until with various maxsizes and True/False
    for with_delimiter.
    """

    delim = b'\r\n'
    for with_delim in (True, False):
        if with_delim:
            cond_delim = b'\r\n'
        else:
            cond_delim = b''

        empty = b''
        small_one = b'1'
        big_two = b'2' * 2048
        for ms in (3, 5, 1024, None):
            x, y = socket.socketpair()
            bs = BufferedSocket(x)

            y.sendall(empty + delim)
            y.sendall(small_one + delim)
            y.sendall(big_two + delim)

            kwargs = {'maxsize': ms, 'with_delimiter': with_delim}
            assert bs.recv_until(delim, **kwargs) == empty + cond_delim
            assert bs.recv_until(delim, **kwargs) == small_one + cond_delim
            try:
                assert bs.recv_until(delim, **kwargs) == big_two + cond_delim
            except MessageTooLong:
                if ms is None:
                    assert False, 'unexpected MessageTooLong'
            else:
                if ms is not None:
                    assert False, 'expected MessageTooLong'

    return


def test_props():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    assert bs.type == x.type
    assert bs.proto == x.proto
    assert bs.family == x.family
    return


def test_buffers():
    x, y = socket.socketpair()
    bx, by = BufferedSocket(x), BufferedSocket(y)

    assert by.getrecvbuffer() == b''
    assert by.getsendbuffer() == b''

    assert bx.getrecvbuffer() == b''

    by.buffer(b'12')
    by.sendall(b'3')
    assert bx.recv_size(1) == b'1'

    assert bx.getrecvbuffer() == b'23'

    return

IS_PYPY_2 = ('__pypy__' in sys.builtin_module_names
             and sys.version_info[0] == 2)
@pytest.mark.xfail(IS_PYPY_2, reason="pypy2 bug, fixed in 7.2. unmark when this test stops failing on travis (when they upgrade from 7.1)")
def test_client_disconnecting():
    def get_bs_pair():
        x, y = socket.socketpair()
        bx, by = BufferedSocket(x), BufferedSocket(y)

        # sanity check
        by.sendall(b'123')
        bx.recv_size(3) == b'123'

        return bx, by

    bx, by = get_bs_pair()
    assert bx.fileno() > 0

    bx.close()
    assert bx.getrecvbuffer() == b''

    try:
        bx.recv(1)
    except socket.error:
        pass
    else:
        assert False, 'expected socket.error on closed recv'

    assert bx.fileno() == -1

    by.buffer(b'123')
    assert by.getsendbuffer()
    try:
        by.flush()
    except socket.error:
        assert by.getsendbuffer() == b'123'
    else:
        if sys.platform != 'win32':  # Windows socketpairs are kind of bad
            assert False, 'expected socket.error broken pipe'

    try:
        by.shutdown(socket.SHUT_RDWR)
    except socket.error:
        # Mac sockets are already shut down at this point. See #71.
        if sys.platform != 'darwin':
            raise

    by.close()
    assert not by.getsendbuffer()

    try:
        by.send(b'123')
    except socket.error:
        pass
    else:
        assert False, 'expected socket.error on closed send'

    return


def test_split_delim():
    delim = b'\r\n'
    first = b'1234\r'
    second = b'\n5'

    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    y.sendall(first)
    try:
        bs.recv_until(delim, timeout=0.0001)
    except Timeout:
        pass
    y.sendall(second)

    assert bs.recv_until(delim, with_delimiter=True) == b'1234\r\n'
    assert bs.recv_size(1) == b'5'
    return


def test_basic_nonblocking():
    delim = b'\n'

    # test with per-call timeout
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    try:
        bs.recv_until(delim, timeout=0)
    except socket.error as se:
        assert se.errno == errno.EWOULDBLOCK
    y.sendall(delim)  # sending an empty message, effectively
    assert bs.recv_until(delim) == b''

    # test with instance-level default timeout
    x, y = socket.socketpair()
    bs = BufferedSocket(x, timeout=0)

    try:
        bs.recv_until(delim)
    except socket.error as se:
        assert se.errno == errno.EWOULDBLOCK
    y.sendall(delim)
    assert bs.recv_until(delim) == b''

    # test with setblocking(0) on the underlying socket
    x, y = socket.socketpair()
    x.setblocking(0)
    bs = BufferedSocket(x)

    try:
        bs.recv_until(delim)
    except socket.error as se:
        assert se.errno == errno.EWOULDBLOCK
    y.sendall(delim)
    assert bs.recv_until(delim) == b''

    return


def test_simple_buffered_socket_passthroughs():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    assert bs.getsockname() == x.getsockname()
    assert bs.getpeername() == x.getpeername()


def test_timeout_setters_getters():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    assert bs.settimeout(1.0) is None
    assert bs.gettimeout() == 1.0

    assert bs.setblocking(False) is None
    assert bs.gettimeout() == 0.0

    assert bs.setblocking(True) is None
    assert bs.gettimeout() is None


def netstring_server(server_socket):
    "A basic netstring server loop, supporting a few operations"
    try:
        while True:
            clientsock, addr = server_socket.accept()
            client = NetstringSocket(clientsock)
            while 1:
                request = client.read_ns()
                if request == b'close':
                    clientsock.close()
                    break
                elif request == b'shutdown':
                    return
                elif request == b'reply4k':
                    client.write_ns(b'a' * 4096)
                elif request == b'ping':
                    client.write_ns(b'pong')
                elif request == b'reply128k':
                    client.setmaxsize(128 * 1024)
                    client.write_ns(b'huge' * 32 * 1024)  # 128kb
                    client.setmaxsize(32768)  # back to default
    except Exception as e:
        print(u'netstring_server exiting with error: %r' % e)
        raise


def test_socketutils_netstring():
    """A holistic feature test of BufferedSocket via the NetstringSocket
    wrapper. Runs
    """
    print("running self tests")

    # Set up server
    server_socket = socket.socket()
    server_socket.bind(('127.0.0.1', 0))  # localhost with ephemeral port
    server_socket.listen(100)
    ip, port = server_socket.getsockname()
    start_server = lambda: netstring_server(server_socket)
    threading.Thread(target=start_server).start()

    # set up client
    def client_connect():
        clientsock = socket.create_connection((ip, port))
        client = NetstringSocket(clientsock)
        return client

    # connect, ping-pong
    client = client_connect()
    client.write_ns(b'ping')
    assert client.read_ns() == b'pong'
    s = time.time()
    for i in range(1000):
        client.write_ns(b'ping')
        assert client.read_ns() == b'pong'
    dur = time.time() - s
    print("netstring ping-pong latency", dur, "ms")

    s = time.time()
    for i in range(1000):
        client.write_ns(b'ping')
    resps = []
    for i in range(1000):
        resps.append(client.read_ns())
    e = time.time()
    assert all([r == b'pong' for r in resps])
    assert client.bsock.getrecvbuffer() == b''
    dur = e - s
    print("netstring pipelined ping-pong latency", dur, "ms")

    # tell the server to close the socket and then try a failure case
    client.write_ns(b'close')
    try:
        client.read_ns()
        raise Exception('read from closed socket')
    except ConnectionClosed:
        print("raised ConnectionClosed correctly")

    # test big messages
    client = client_connect()
    client.setmaxsize(128 * 1024)
    client.write_ns(b'reply128k')
    res = client.read_ns()
    assert len(res) == (128 * 1024)
    client.write_ns(b'close')

    # test that read timeouts work
    client = client_connect()
    client.settimeout(0.1)
    try:
        client.read_ns()
        raise Exception('did not timeout')
    except Timeout:
        print("read_ns raised timeout correctly")
    client.write_ns(b'close')

    # test that netstring max sizes work
    client = client_connect()
    client.setmaxsize(2048)
    client.write_ns(b'reply4k')
    try:
        client.read_ns()
        raise Exception('read more than maxsize')
    except NetstringMessageTooLong:
        print("raised MessageTooLong correctly")
    try:
        client.bsock.recv_until(b'b', maxsize=4096)
        raise Exception('recv_until did not raise MessageTooLong')
    except MessageTooLong:
        print("raised MessageTooLong correctly")
    assert client.bsock.recv_size(4097) == b'a' * 4096 + b','
    print('correctly maintained buffer after exception raised')

    # test BufferedSocket read timeouts with recv_until and recv_size
    client.bsock.settimeout(0.01)
    try:
        client.bsock.recv_until(b'a')
        raise Exception('recv_until did not raise Timeout')
    except Timeout:
        print('recv_until correctly raised Timeout')
    try:
        client.bsock.recv_size(1)
        raise Exception('recv_size did not raise Timeout')
    except Timeout:
        print('recv_size correctly raised Timeout')

    client.write_ns(b'shutdown')
    print("all passed")


def netstring_server_timeout_override(server_socket):
    """Netstring socket has an unreasonably low timeout,
    however it should be overridden by the `read_ns` argument."""

    try:
        while True:
            clientsock, addr = server_socket.accept()
            client = NetstringSocket(clientsock, timeout=0.01)
            while 1:
                request = client.read_ns(1)
                if request == b'close':
                    clientsock.close()
                    break
                elif request == b'shutdown':
                    return
                elif request == b'ping':
                    client.write_ns(b'pong')
    except Exception as e:
        print(u'netstring_server exiting with error: %r' % e)
        raise


def test_socketutils_netstring_timeout():
    """Tests that server socket timeout is overridden by the argument to read call.

    Server has timeout of 10 ms, and we will sleep for 20 ms. If timeout is not overridden correctly,
    a timeout exception will be raised."""

    print("running timeout test")

    # Set up server
    server_socket = socket.socket()
    server_socket.bind(('127.0.0.1', 0))  # localhost with ephemeral port
    server_socket.listen(100)
    ip, port = server_socket.getsockname()
    start_server = lambda: netstring_server_timeout_override(server_socket)
    threading.Thread(target=start_server).start()

    # set up client
    def client_connect():
        clientsock = socket.create_connection((ip, port))
        client = NetstringSocket(clientsock)
        return client

    # connect, ping-pong
    client = client_connect()
    time.sleep(0.02)
    client.write_ns(b'ping')
    assert client.read_ns() == b'pong'

    client.write_ns(b'shutdown')
    print("no timeout occurred - all good.")