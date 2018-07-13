from phxd.utils import HLCharConst

from datetime import datetime
from struct import pack, unpack
import re


class HLException (Exception):
    """ Exception thrown due to protocol errors. """

    def __init__(self, msg="Unknown exception.", fatal=False):
        self.msg = msg
        self.fatal = fatal

    def __str__(self):
        return self.msg


class HLAccount (object):
    """ Stores account information. """

    def __init__(self, login=""):
        self.id = 0
        self.login = login
        self.password = ""
        self.name = ""
        self.privs = 0
        self.fileRoot = ""
        self.profile = ""

    def __str__(self):
        return "<HLAccount '%s'>" % self.login

    def hasPriv(self, priv):
        return ((int(self.privs) & priv) > 0)


class HLNewsPost (object):
    """ Stores information about a single news post. """

    def __init__(self, nick="", login="", body=""):
        self.id = 0
        self.nick = nick
        self.login = login
        self.body = body
        self.date = datetime.now()


class HLMail (object):
    """ Stores information about a mail message. """

    def __init__(self, to_login="", from_login="", msg=""):
        self.to_login = to_login
        self.from_login = from_login
        self.message = msg
        self.sent = datetime.now()

    def __str__(self):
        return '<HLMail From:"%s" To:"%s" Message:"%s">' % (self.from_login, self.to_login, self.message)


class HLUser:
    """ Stores user information, along with an associated HLAccount object. Also flattenable for use in userlist packet objects. """

    def __init__(self, uid=0, addr=""):
        self.uid = uid
        self.ip = addr
        self._nick = "unnamed"
        self.icon = 500
        self.status = 0
        self.gif = ""
        self.color = -1
        self.account = None
        self.away = False
        self.lastPacketTime = 0.0
        self.valid = False

    def _getNick(self):
        return self._nick

    def _setNick(self, n):
        self._nick = re.sub(r'[:<>]', '', n)
    nick = property(_getNick, _setNick)

    def __str__(self):
        rep = "<%s:" % self.nick
        if self.account:
            rep = rep + self.account.login
        return rep + ">"

    def hasPriv(self, priv):
        """ Returns True if the account associated with the user has the specified privilege. """
        return self.account and self.account.hasPriv(priv)

    def parse(self, data):
        if len(data) < 8:
            return 0
        (self.uid, self.icon, self.status, nicklen) = unpack("!4H", data[0:8])
        if (len(data) - 8) < nicklen:
            return 0
        self.nick = data[8:8 + nicklen]
        if (len(data) - 8 - nicklen) >= 4:
            self.color = unpack("!L", data[8 + nicklen:12 + nicklen])[0]
            return (12 + nicklen)
        return (8 + nicklen)

    def flatten(self):
        """ Flattens the user information into a packed structure to send in a HLObject. """
        nick_utf8 = self.nick.encode('utf-8', 'replace')
        data = pack("!4H", self.uid, self.icon, self.status, len(nick_utf8))
        data += nick_utf8
        # this is an avaraline extension for nick coloring
        if self.color >= 0:
            data += pack("!L", self.color)
        return data


class HLChat:
    """ Stores information about a private chat. """

    def __init__(self, id=0):
        self.id = id
        self.users = []
        self.invites = []
        self.subject = ""

    def addUser(self, user):
        """ Adds the specified user to this chat. """
        self.users.append(user)

    def addInvite(self, user):
        """ Adds the specified user to the list of invitees for this chat. """
        self.invites.append(user.uid)

    def removeUser(self, user):
        """ Removes the specified user from this chat. """
        self.users.remove(user)

    def removeInvite(self, user):
        """ Removes the specified user from the list of invitees for this chat. """
        self.invites.remove(user.uid)

    def hasUser(self, user):
        """ Returns True if this chat has the specified user in it. """
        for u in self.users:
            if u.uid == user.uid:
                return True
        return False

    def hasInvite(self, user):
        """ Returns True if this chat has the specified user in its list of invitees. """
        for uid in self.invites:
            if user.uid == uid:
                return True
        return False


class HLResumeData:
    """ Stores transfer resume data (offsets for each fork type). """

    def __init__(self, data=None):
        self.forkOffsets = {}
        self.forkCount = 0
        if (data is not None) and (len(data) >= 42):
            self._parseResumeData(data)

    def forkOffset(self, fork):
        """ Returns the offset for the specified fork type. """
        if fork in self.forkOffsets:
            return self.forkOffsets[fork]
        return 0

    def setForkOffset(self, fork, offset):
        """ Sets the offset for the specified fork type. """
        self.forkOffsets[fork] = offset

    def _parseResumeData(self, data):
        """ Parses the specified packed structure data into this resume data object. """
        (format, version) = unpack("!LH", data[0:6])
        _reserved = data[6:40]  # NOQA
        self.forkCount = unpack("!H", data[40:42])[0]
        for k in range(self.forkCount):
            offset = 42 + (16 * k)
            subData = data[offset:offset + 8]
            if len(subData) == 8:
                (forkType, forkOffset) = unpack("!2L", subData)
                self.forkOffsets[forkType] = forkOffset

    def flatten(self):
        """ Flattens the resume information into a packed structure to send in a HLObject. """
        data = pack("!LH", HLCharConst("RFLT"), 1)
        data += bytes(34)
        data += pack("!H", len(self.forkOffsets.keys()))
        for forkType in self.forkOffsets.keys():
            data += pack("!4L", forkType, self.forkOffsets[forkType], 0, 0)
        return data
