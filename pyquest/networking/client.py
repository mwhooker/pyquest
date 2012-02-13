import asyncore, asynchat, socket
import json
import sys


class ChatClient(asynchat.async_chat):

    def __init__(self, host, port, username="Matt"):
        asynchat.async_chat.__init__(self)
        self.username = username
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect( (host, port) )
        self.ibuffer = []
        self.set_terminator("\r\n\r\n")

    def collect_incoming_data(self, data):
        """Buffer the data"""
        self.ibuffer.append(data)

    def handle_connect(self):
        print "Now chatting"
        self._send_data("connect", username=self.username)

    def handle_close(self):
        print "goodbye"
        self.close()
        sys.exit(0)

    def found_terminator(self):
        if self.ibuffer:
            msg = ''.join(self.ibuffer)
            msg = json.loads(msg)
            self.ibuffer = []
            #self.queue.put_nowait(msg)
            print "[%s] %s" % (msg['from'], msg['body'])

    def _send_data(self, type_, **kwargs):
        d = {}
        d.update(kwargs)
        d['type'] = type_
        msg = json.dumps(d)
        msg += self.get_terminator()
        self.push(msg)

    def send_msg(self, msg):
        self._send_data("msg", body=msg)


class Input(asyncore.file_dispatcher):

    def __init__(self, client):
        asyncore.file_dispatcher.__init__(self, sys.stdin)
        self.client = client

    def handle_read(self):
        self.client.send_msg(self.recv(1024))


if __name__ == '__main__':
    client = ChatClient('localhost', 51234, sys.argv[1])
    inp_dispatcher = Input(client)

    asyncore.loop(use_poll=True)
