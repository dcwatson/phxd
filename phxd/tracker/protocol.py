from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol, Protocol

from struct import pack, unpack
import io
import re


class HLTrackerProtocol (Protocol):

    buffer = ""

    def dataReceived(self, data):
        self.buffer += data
        if len(self.buffer) >= 6:
            (magic, version) = unpack("!LH", self.buffer[0:6])
            self.factory.notifyMagic(self, version)
            self.buffer = self.buffer[6:]


class TrackerListener (DatagramProtocol):

    def __init__(self, tracker):
        self.tracker = tracker

    def datagramReceived(self, data, addr):
        buf = io.StringIO(data)
        (cmd, port, users, zero, server_id) = unpack("!4HL", buf.read(12))
        name_len = ord(buf.read(1))
        name = buf.read(name_len)
        desc_len = ord(buf.read(1))
        desc = buf.read(desc_len)
        # passwd_len = ord(buf.read(1))
        # passwd = buf.read(passwd_len)
        self.tracker.addServer(server_id, name, desc, addr[0], port, users)


class TrackerPinger (DatagramProtocol):

    def __init__(self, tracker_ip, tracker_port, server_id, name, desc, port, users, passwd=""):
        self.tracker_ip, self.tracker_port = tracker_ip, tracker_port
        namedata = name.encode('utf-8')
        descdata = desc.encode('utf-8')
        passdata = passwd.encode('utf-8')
        self.data = pack("!4HL", 1, port, users, 0, server_id)
        self.data += bytes([len(namedata)])
        self.data += namedata
        self.data += bytes([len(descdata)])
        self.data += descdata
        self.data += bytes([len(passdata)])
        self.data += passdata

    def doSend(self, ip):
        self.transport.connect(ip, self.tracker_port)
        self.transport.write(self.data)

    def startProtocol(self):
        if re.search(r'[a-zA-Z]', self.tracker_ip):
            reactor.resolve(self.tracker_ip).addCallback(self.doSend)
        else:
            self.doSend(self.tracker_ip)
