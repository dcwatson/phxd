from datetime import datetime, timedelta
from struct import pack, unpack
import time


def decodeString(data):
    ret = None
    try:
        # First, try to decode using UTF-8
        ret = data.decode('utf-8')
    except:
        # If that fails, the client *probably* sent MacRoman
        try:
            ret = data.decode('mac_roman')
        except:
            # If all else fails, decode as UTF-8, replacing uknown chars
            ret = data.decode('utf-8', 'replace')
    return ret


def HLCharConst(s):
    """ Returns the numeric equivalent of a 4-character string (OSType in classic Mac OS).
    Used for file types, creator codes, and magic numbers. """
    if len(s) != 4:
        return 0
    return 0 + (ord(s[0]) << 24) + (ord(s[1]) << 16) + (ord(s[2]) << 8) + ord(s[3])


def HLDecodeConst(n):
    return chr((n & 0xFF000000) >> 24) + chr((n & 0x00FF0000) >> 16) + chr((n & 0x0000FF00) >> 8) + chr(n & 0x000000FF)


def HLEncode(s, encoding='utf-8'):
    if s is not None:
        utf8 = s.encode(encoding)
        return bytes(255 - n for n in utf8)
    return None


def HLDecode(b):
    if b is not None:
        return decodeString(bytes(255 - n for n in b))
    return None


def HLServerMagic(code=0):
    return pack("!2L", HLCharConst("TRTP"), code)


def HLClientMagic(major=1, minor=2):
    return pack("!LLHH", HLCharConst("TRTP"), HLCharConst("HOTL"), major, minor)


def HLEncodeDate(d):
    epoch = time.gmtime(0)[0]
    secs = int(time.mktime(d.utctimetuple())) - time.timezone
    data = pack("!HHL", epoch, 0, secs)
    return data


def HLDecodeDate(data):
    (epoch, milli, secs) = unpack("!HHL", data[0:8])
    delta = timedelta(seconds=secs)
    start = datetime(epoch, 1, 1)
    return start + delta


def formatElapsedTime(elapsed):
    secs = int(elapsed)
    days = secs / 86400
    secs -= (days * 86400)
    hours = secs / 3600
    secs -= (hours * 3600)
    mins = secs / 60
    secs -= (mins * 60)
    if days > 0:
        return "%dd:%02dh:%02dm:%02ds" % (days, hours, mins, secs)
    if mins > 0:
        return "%02dh:%02dm:%02ds" % (hours, mins, secs)
    return "%d seconds" % secs
