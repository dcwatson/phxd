from twisted.internet import reactor
from twisted.internet.protocol import Factory

from phxd.constants import *
from phxd.tracker.protocol import *
from phxd.utils import HLCharConst

from struct import pack
import socket
import time


class TrackerEntry:

    name = "unnamed server"
    description = "no description"
    ip = "127.0.0.1"
    port = 5500
    users = 13
    last_update = None

    def __init__(self, name, desc, ip, port, users):
        self.name, self.description, self.ip, self.port, self.users = name, desc, ip, port, users
        self.last_update = time.time()

    def flatten(self):
        data = socket.inet_aton(self.ip)
        data += pack("!3H", self.port, self.users, 0)
        data += chr(len(self.name))
        data += self.name
        data += chr(len(self.description))
        data += self.description
        return data


class HLTracker (Factory):

    protocol = HLTrackerProtocol

    def __init__(self, timeout=300):
        self.servers = {}
        self.timeout = timeout

    def start(self, tcp_port=TRACKER_TCP_PORT, udp_port=TRACKER_UDP_PORT):
        reactor.listenTCP(tcp_port, self)
        reactor.listenUDP(udp_port, TrackerListener(self))
        reactor.callLater(300, self.pruneServers)

    def notifyMagic(self, conn, version):
        if version < 2:
            data = pack("!2H", len(self.servers), len(self.servers))
            for s in self.servers.values():
                data += s.flatten()
            conn.transport.write(pack("!LH", HLCharConst("HTRK"), 1))
            conn.transport.write(pack("!2H", 1, len(data)))
            conn.transport.write(data)
        else:
            conn.transport.loseConnection()

    def addServer(self, server_id, name, desc, ip, port, users):
        if server_id in self.servers:
            self.servers[server_id].name = name
            self.servers[server_id].description = desc
            self.servers[server_id].ip = ip
            self.servers[server_id].port = port
            self.servers[server_id].users = users
            self.servers[server_id].last_update = time.time()
        else:
            self.servers[server_id] = TrackerEntry(name, desc, ip, port, users)

    def pruneServers(self):
        dead_ids = []
        for (server_id, server) in self.servers.items():
            elapsed = time.time() - server.last_update
            if elapsed > self.timeout:
                dead_ids.append(server_id)
        for id in dead_ids:
            del self.servers[id]
        reactor.callLater(300, self.pruneServers)


def send_update(tracker_ip, tracker_port, server_id, name, desc, port, users, passwd=""):
    pinger = TrackerPinger(tracker_ip, tracker_port, server_id, name, desc, port, users, passwd)
    reactor.listenUDP(0, pinger)
