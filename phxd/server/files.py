from pydispatch import dispatcher
from twisted.internet import task
from twisted.internet.protocol import Factory

from phxd.protocol import HLTransferProtocol
from phxd.server.config import conf
from phxd.server.signals import *
from phxd.transfer import HLIncomingTransfer, HLOutgoingTransfer

import logging
import time


class HLDownload (HLOutgoingTransfer):
    def __str__(self):
        kps = self.getTotalBPS() / 1024
        return "[DL] %s @ %sk/sec (%s%%)" % (self.file.name, kps, self.overallPercent())


class HLUpload (HLIncomingTransfer):
    def __str__(self):
        kps = self.getTotalBPS() / 1024
        return "[UL] %s @ %sk/sec (%s%%)" % (self.file.name, kps, self.overallPercent())


class HLFileServer (Factory):

    protocol = HLTransferProtocol

    def __init__(self, hlserver):
        self.lastTransferID = 0
        self.transfers = []
        self.server = hlserver
        self.tickle = task.LoopingCall(self.checkTransfers)
        self.tickle.start(5.0, False)

    # Notification methods called from HLTransferProtocol

    def notifyConnect(self, conn):
        pass

    def notifyDisconnect(self, conn):
        if conn.info in self.transfers:
            if conn.info.isComplete():
                logging.info("[xfer] completed %s", conn.info)
                dispatcher.send(signal=transfer_completed, sender=self, server=self.server, transfer=conn.info)
                self.transfers.remove(conn.info)
            else:
                logging.info("[xfer] aborted %s", conn.info)
                dispatcher.send(signal=transfer_aborted, sender=self, server=self.server, transfer=conn.info)
                self.transfers.remove(conn.info)

    def notifyMagic(self, conn, xfid, size, flags):
        for x in self.transfers:
            if x.id == xfid:
                if x.isIncoming() and x.total == 0:
                    x.total = size
                conn.start(x)
                dispatcher.send(signal=transfer_started, sender=self, server=self.server, transfer=x)

    # Convenience methods called from the file handler

    def addUpload(self, user, file):
        self.lastTransferID += 1
        info = HLUpload(self.lastTransferID, file)
        info.owner = user.uid
        self.transfers.append(info)
        return info

    def addDownload(self, user, file, resume):
        self.lastTransferID += 1
        info = HLDownload(self.lastTransferID, file, resume)
        info.owner = user.uid
        self.transfers.append(info)
        return info

    def checkTransfers(self):
        # TODO: when a transfer times out, close it's transport connection
        deadlist = []
        now = time.time()
        for x in self.transfers:
            if (now - x.lastActivity) > conf.XFER_TIMEOUT:
                deadlist.append(x)
        for dead in deadlist:
            logging.info("[xfer] timed out %s", dead)
            self.transfers.remove(dead)
