from twisted.internet import reactor

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PRIV_MODIFY_USERS
from phxd.server import handlers


def handle(server, user, arg, ref):
    if len(arg) > 0 and user.hasPriv(PRIV_MODIFY_USERS):
        bits = arg.split()
        cmd = bits[0]
        mod = ""
        if len(bits) > 1:
            mod = bits[1]
        if cmd == "list":
            chat = HLPacket(HTLS_HDR_CHAT)
            chat.addString(DATA_STRING, ", ".join(handlers.__all__))
            server.sendPacket(chat, user)
        elif cmd == "reload":
            # call next time through the event loop to avoid problems
            reactor.callLater(0, handlers.reload, "phxd.server.handlers", mod)
