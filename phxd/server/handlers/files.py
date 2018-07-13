from pydispatch import dispatcher
from twisted.internet import utils

from phxd.constants import *
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *
from phxd.types import HLException, HLResumeData
from phxd.utils import HLCharConst, HLEncodeDate, decodeString

from datetime import datetime
from struct import pack, unpack
import os


def install():
    dispatcher.connect(handleTransferFinished, signal=transfer_completed)


def uninstall():
    dispatcher.disconnect(handleTransferFinished, signal=transfer_completed)


def handleTransferFinished(server, transfer):
    if transfer.isIncoming() and transfer.isComplete() and transfer.path.endswith(".hpf"):
        newPath = transfer.path[:-4]
        os.rename(transfer.path, newPath)
        transfer.path = newPath
        transfer.name = os.path.basename(transfer.path)
        if conf.UPLOAD_SCRIPT:
            user = server.getUser(transfer.owner)
            pargs = [
                str(transfer.path),
            ]
            environ = {
                'USER_LOGIN': str(user.account.login),
                'USER_NICK': str(user.nick),
                'USER_IPADDR': str(user.ip),
            }
            utils.getProcessOutput(conf.UPLOAD_SCRIPT, args=pargs, env=environ)


def parseDir(d):
    parts = []
    if (d is None) or (len(d) < 5):
        return parts
    pos = 0
    count = unpack("!H", d[pos:pos + 2])[0]
    pos += 3
    while (pos < len(d)) and (count > 0):
        size = unpack("!H", d[pos:pos + 2])[0]
        pos += 2
        parts.append(decodeString(d[pos:pos + size]))
        pos += size + 1
        count -= 1
    return parts


def buildPath(root, d, file=None):
    """ Build a path from a root directory, an array of directory parts, and a filename. Filter out any references to .. """
    pathArray = []
    if root:
        pathArray.append(root)
    else:
        pathArray.append(conf.FILE_ROOT)
    for part in d:
        if (len(part) > 0) and (part != ".."):
            pathArray.append(part)
    if (file is not None) and (len(file) > 0):
        pathArray.append(file)
    return os.path.join(*pathArray)


def getFileType(path):
    if os.path.isdir(path):
        return HLCharConst("fldr")
    elif path.endswith(".hpf"):
        return HLCharConst("HTft")
    else:
        return HLCharConst("????")


def getFileCreator(path):
    if os.path.isdir(path):
        return 0
    elif path.endswith(".hpf"):
        return HLCharConst("HTLC")
    else:
        return HLCharConst("????")

# handler methods


@packet_handler(HTLC_HDR_FILE_LIST)
def handleFileList(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    path = buildPath(user.account.fileRoot, dir)

    if not os.path.exists(path):
        raise HLException("The specified directory does not exist.")
    if not os.path.isdir(path):
        raise HLException("The specified path is not a directory.")
    if (not user.hasPriv(PRIV_VIEW_DROPBOXES)) and (path.upper().find("DROP BOX") >= 0):
        raise HLException("You are not allowed to view drop boxes.")

    reply = packet.response()
    files = os.listdir(path)
    files.sort()
    for fname in files:
        if conf.SHOW_DOTFILES or (fname[0] != '.'):
            # Only list files starting with . if SHOW_DOTFILES is True.
            fpath = os.path.join(path, fname)
            type = getFileType(fpath)
            creator = getFileCreator(fpath)
            if os.path.isdir(fpath):
                size = len(os.listdir(fpath))
            else:
                size = os.path.getsize(fpath)
            namedata = fname.encode('utf-8')
            data = pack("!5L", type, creator, size, size, len(namedata)) + namedata
            reply.addBinary(DATA_FILE, data)
    server.sendPacket(reply, user)


@packet_handler(HTLC_HDR_FILE_GET)
@require_permission(PRIV_DOWNLOAD_FILES, "download files")
def handleFileDownload(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    name = packet.getString(DATA_FILENAME, "")
    resume = HLResumeData(packet.getBinary(DATA_RESUME))
    # options = packet.getNumber(DATA_XFEROPTIONS, 0)

    path = buildPath(user.account.fileRoot, dir, name)
    if not os.path.exists(path):
        raise HLException("Specified file does not exist.")

    offset = resume.forkOffset(HLCharConst("DATA"))
    xfer = server.fileserver.addDownload(user, path, offset)
    dataSize = os.path.getsize(path) - offset

    reply = packet.response()
    reply.addNumber(DATA_XFERSIZE, xfer.total)
    reply.addNumber(DATA_FILESIZE, dataSize)
    reply.addNumber(DATA_XFERID, xfer.id)
    server.sendPacket(reply, user)


@packet_handler(HTLC_HDR_FILE_PUT)
@require_permission(PRIV_UPLOAD_FILES, "upload files")
def handleFileUpload(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    name = packet.getString(DATA_FILENAME, "")
    size = packet.getNumber(DATA_XFERSIZE, 0)
    # options = packet.getNumber(DATA_XFEROPTIONS, 0)

    path = buildPath(user.account.fileRoot, dir, name)
    if os.path.exists(path):
        raise HLException("File already exists.")
    if (not user.hasPriv(PRIV_UPLOAD_ANYWHERE)) and (path.upper().find("UPLOAD") < 0 or path.upper().find("DROP BOX") < 0):
        raise HLException("You must upload to an upload directory or drop box.")

    # Make sure we have enough disk space to accept the file.
    upDir = buildPath(user.account.fileRoot, dir)
    info = os.statvfs(upDir)
    free = info.f_bavail * info.f_frsize
    if size >= free:
        raise HLException("Insufficient disk space.")

    # All uploads in progress should have this extension.
    path += ".hpf"

    xfer = server.fileserver.addUpload(user, path)
    xfer.total = size

    reply = packet.response()
    reply.addNumber(DATA_XFERID, xfer.id)
    if os.path.exists(path):
        resume = HLResumeData()
        resume.setForkOffset(HLCharConst("DATA"), os.path.getsize(path))
        reply.addBinary(DATA_RESUME, resume.flatten())
    server.sendPacket(reply, user)


@packet_handler(HTLC_HDR_FILE_DELETE)
def handleFileDelete(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    name = packet.getString(DATA_FILENAME, "")
    path = buildPath(user.account.fileRoot, dir, name)
    if not os.path.exists(path):
        raise HLException("Specified file or directory does not exist.")
    if os.path.isdir(path):
        if not user.hasPriv(PRIV_DELETE_FOLDERS):
            raise HLException("You are not allowed to delete folders.")
        # First, recursively delete everything inside the directory.
        for (root, dirs, files) in os.walk(path, topdown=False):
            for name in files:
                os.unlink(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        # Then delete the directory itself.
        os.rmdir(path)
    else:
        if not user.hasPriv(PRIV_DELETE_FILES):
            raise HLException("You are not allowed to delete files.")
        os.unlink(path)
    server.sendPacket(packet.response(), user)


@packet_handler(HTLC_HDR_FILE_MKDIR)
@require_permission(PRIV_CREATE_FOLDERS, "create folders")
def handleFolderCreate(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    name = packet.getString(DATA_FILENAME, "")
    path = buildPath(user.account.fileRoot, dir, name)
    if os.path.exists(path):
        raise HLException("Specified directory already exists.")
    os.mkdir(path, conf.DIR_UMASK)
    server.sendPacket(packet.response(), user)


@packet_handler(HTLC_HDR_FILE_MOVE)
@require_permission(PRIV_MOVE_FILES, "move files")
def handleFileMove(server, user, packet):
    oldDir = parseDir(packet.getBinary(DATA_DIR))
    newDir = parseDir(packet.getBinary(DATA_NEWDIR))
    name = packet.getString(DATA_FILENAME, "")

    oldPath = buildPath(user.account.fileRoot, oldDir, name)
    newPath = buildPath(user.account.fileRoot, newDir, name)

    if not os.path.exists(oldPath):
        raise HLException("Invalid file or directory.")
    if os.path.exists(newPath):
        raise HLException("The specified file already exists in the new location.")

    os.rename(oldPath, newPath)
    server.sendPacket(packet.response(), user)


@packet_handler(HTLC_HDR_FILE_GETINFO)
def handleFileGetInfo(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    name = packet.getString(DATA_FILENAME, b"")

    path = buildPath(user.account.fileRoot, dir, name)
    if not os.path.exists(path):
        raise HLException("No such file or directory.")

    d = datetime.fromtimestamp(os.path.getmtime(path))

    info = packet.response()
    info.addString(DATA_FILENAME, name)
    info.addNumber(DATA_FILESIZE, os.path.getsize(path))
    info.addNumber(DATA_FILETYPE, getFileType(path))
    info.addNumber(DATA_FILECREATOR, getFileCreator(path))
    info.addBinary(DATA_DATECREATED, HLEncodeDate(d))
    info.addBinary(DATA_DATEMODIFIED, HLEncodeDate(d))
    server.sendPacket(info, user)


@packet_handler(HTLC_HDR_FILE_SETINFO)
def handleFileSetInfo(server, user, packet):
    dir = parseDir(packet.getBinary(DATA_DIR))
    oldName = packet.getString(DATA_FILENAME, "")
    newName = packet.getString(DATA_NEWFILE, oldName)

    if (oldName != newName) and (not user.hasPriv(PRIV_RENAME_FILES)):
        raise HLException("You cannot rename files.")

    oldPath = buildPath(user.account.fileRoot, dir, oldName)
    newPath = buildPath(user.account.fileRoot, dir, newName)

    if not os.path.exists(oldPath):
        raise HLException("Invalid file or directory.")
    if (oldPath != newPath) and os.path.exists(newPath):
        raise HLException("The specified file already exists.")

    os.rename(oldPath, newPath)
    server.sendPacket(packet.response(), user)
