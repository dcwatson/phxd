from phxd.constants import *
from phxd.packet import HLPacket

import time


def handle(server, user, args, ref):
    secs = int(time.time() - server.startTime)
    days = secs / 86400
    secs -= (days * 86400)
    hours = secs / 3600
    secs -= (hours * 3600)
    mins = secs / 60
    secs -= (mins * 60)
    str = "\r > Uptime: %d days, %d hours, %d minutes, and %d seconds." % (days, hours, mins, secs)
    chat = HLPacket(HTLS_HDR_CHAT)
    chat.addString(DATA_STRING, str)
    if ref > 0:
        chat.addInt32(DATA_CHATID, ref)
    server.sendPacket(chat, user)
