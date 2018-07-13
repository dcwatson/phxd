from pydispatch import dispatcher

from phxd.constants import *
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *

import codecs
import os
import time


class RollingLog:

    logday = 0
    logdir = ""
    logfile = None

    def __init__(self, logdir):
        self.logdir = logdir

    def rotate(self):
        now = time.localtime()
        name = "%04d-%02d-%02d.txt" % (now[0], now[1], now[2])
        self.logday = now[7]
        if self.logfile:
            self.logfile.close()
        path = os.path.join(self.logdir, name)
        self.logfile = codecs.open(path, "a", "utf-8")

    def writeLine(self, line):
        now = time.localtime()
        if now[7] != self.logday:
            self.rotate()
        out = "%02d:%02d:%02d\t%s\n" % (now[3], now[4], now[5], line.strip())
        self.logfile.write(out)
        self.logfile.flush()


class ChatLog (RollingLog):

    def __init__(self, logdir):
        RollingLog.__init__(self, logdir)

    def write(self, user, logtype, line=""):
        self.writeLine("%s\t%s\t%s\t%s" % (user.account.login, user.nick, logtype, line))

    def chat(self, user, chat):
        self.write(user, "CHAT", chat)

    def emote(self, user, chat):
        self.write(user, "EMOTE", chat)

    def join(self, user):
        self.write(user, "JOIN")

    def change(self, user, oldNick):
        self.write(user, "CHANGE", oldNick)

    def leave(self, user):
        self.write(user, "LEAVE")


chatlog = ChatLog(conf.LOG_DIR)


def install():
    dispatcher.connect(logUserJoin, signal=user_login)
    dispatcher.connect(logUserChange, signal=user_change)
    dispatcher.connect(logUserLeave, signal=user_leave)


def uninstall():
    dispatcher.disconnect(logUserJoin, signal=user_login)
    dispatcher.disconnect(logUserChange, signal=user_change)
    dispatcher.disconnect(logUserLeave, signal=user_leave)
    if chatlog.logfile:
        chatlog.logfile.close()


@packet_filter(HTLS_HDR_CHAT)
def logChat(server, packet, users):
    private = packet.getNumber(DATA_CHATID, 0) > 0
    user = server.getUser(packet.getNumber(DATA_UID))
    if conf.LOG_CHAT and user is not None and not private:
        line = packet.getString(DATA_STRING)
        prefix = packet.getNumber(DATA_OFFSET, 0)
        emote = packet.getNumber(DATA_OPTION, 0) > 0
        if emote:
            chatlog.emote(user, line[prefix:])
        else:
            chatlog.chat(user, line[prefix:])


def logUserJoin(server, user):
    if conf.LOG_CHAT:
        chatlog.join(user)


def logUserChange(server, user, oldNick):
    if conf.LOG_CHAT and (user.nick != oldNick):
        chatlog.change(user, oldNick)


def logUserLeave(server, user):
    if conf.LOG_CHAT:
        chatlog.leave(user)
