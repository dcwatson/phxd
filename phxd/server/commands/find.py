from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.config import conf

import os


def handle(server, user, arg, ref):
    if len(arg) > 0:
        rootDir = user.account.fileRoot
        if not rootDir:
            rootDir = conf.FILE_ROOT
        pre = len(rootDir)
        matches = []
        for (root, dirs, files) in os.walk(rootDir):
            root = root.decode("utf-8", "replace")
            for name in dirs:
                name = name.decode("utf-8", "replace")
                if arg.upper() in name.upper():
                    matches.append("+ " + os.path.join(root, name)[pre:])
            for name in files:
                name = name.decode("utf-8", "replace")
                if arg.upper() in name.upper():
                    matches.append("- " + os.path.join(root, name)[pre:])
        found = "(none)"
        if len(matches) > 0:
            found = "\r > ".join(matches)
        matchStr = "\r > --- search results for '%s' ------------\r > %s" % (arg, found)
        chat = HLPacket(HTLS_HDR_CHAT)
        chat.addString(DATA_STRING, matchStr)
        if ref > 0:
            chat.addInt32(DATA_CHATID, ref)
        server.sendPacket(chat, user)
