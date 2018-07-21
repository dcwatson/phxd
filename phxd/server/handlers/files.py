from phxd.constants import *
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import packet_handler, require_permission
from phxd.server.signals import transfer_completed
from phxd.types import HLException, HLFile, HLResumeData
from phxd.utils import HLEncodeDate, decode_string

from datetime import datetime
from struct import unpack
import os


def install():
    transfer_completed.connect(handle_transfer_finished)


def uninstall():
    transfer_completed.disconnect(handle_transfer_finished)


def handle_transfer_finished(server, transfer):
    if transfer.incoming and transfer.is_complete():
        if conf.UPLOAD_SCRIPT:
            pargs = [
                transfer.file.dataPath,
            ]
            environ = {
                'USER_LOGIN': str(transfer.owner.account.login),
                'USER_NICK': str(transfer.owner.nick),
                'USER_IPADDR': str(transfer.owner.ip),
            }
            print(conf.UPLOAD_SCRIPT, pargs, environ)
            # utils.getProcessOutput(conf.UPLOAD_SCRIPT, args=pargs, env=environ)


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
        parts.append(decode_string(d[pos:pos + size]))
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


# handler methods


@packet_handler(HTLC_HDR_FILE_LIST)
def handleFileList(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    path = buildPath(user.account.fileRoot, dir)

    if not os.path.exists(path):
        raise HLException("The specified directory does not exist.")
    if not os.path.isdir(path):
        raise HLException("The specified path is not a directory.")
    if (not user.has_perm(PERM_VIEW_DROPBOXES)) and (path.upper().find("DROP BOX") >= 0):
        raise HLException("You are not allowed to view drop boxes.")

    reply = packet.response()
    files = os.listdir(path)
    files.sort()
    for fname in files:
        if conf.SHOW_DOTFILES or (fname[0] != '.'):
            # Only list files starting with . if SHOW_DOTFILES is True.
            file = HLFile(os.path.join(path, fname))
            reply.add(DATA_FILE, file.flatten())
    server.send_packet(reply, user)


@packet_handler(HTLC_HDR_FILE_GET)
@require_permission(PERM_DOWNLOAD_FILES, "download files")
def handleFileDownload(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    name = packet.string(DATA_FILENAME, "")
    resume = HLResumeData(packet.binary(DATA_RESUME))
    # options = packet.number(DATA_XFEROPTIONS, 0)

    path = buildPath(user.account.fileRoot, dir, name)
    if not os.path.exists(path):
        raise HLException("Specified file does not exist.")

    file = HLFile(path)
    xfer = server.add_download(user, file, resume)
    dataSize = file.size() - resume.totalOffset()

    reply = packet.response()
    reply.add_number(DATA_XFERSIZE, xfer.total)
    reply.add_number(DATA_FILESIZE, dataSize)
    reply.add_number(DATA_XFERID, xfer.id)
    server.send_packet(reply, user)


@packet_handler(HTLC_HDR_FILE_PUT)
@require_permission(PERM_UPLOAD_FILES, "upload files")
def handleFileUpload(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    name = packet.string(DATA_FILENAME, "")
    size = packet.number(DATA_XFERSIZE, 0)
    # options = packet.number(DATA_XFEROPTIONS, 0)

    path = buildPath(user.account.fileRoot, dir, name)
    if os.path.exists(path):
        raise HLException("File already exists.")
    if (not user.has_perm(PERM_UPLOAD_ANYWHERE)) and (path.upper().find("UPLOAD") < 0 or path.upper().find("DROP BOX") < 0):
        raise HLException("You must upload to an upload directory or drop box.")

    # Make sure we have enough disk space to accept the file.
    upDir = buildPath(user.account.fileRoot, dir)
    info = os.statvfs(upDir)
    free = info.f_bavail * info.f_frsize
    if size >= free:
        raise HLException("Insufficient disk space.")

    file = HLFile(path)
    xfer = server.add_upload(user, file)
    xfer.total = size

    reply = packet.response()
    reply.add_number(DATA_XFERID, xfer.id)
    if file.exists():
        reply.add(DATA_RESUME, file.resumeData().flatten())
    server.send_packet(reply, user)


@packet_handler(HTLC_HDR_FILE_DELETE)
def handleFileDelete(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    name = packet.string(DATA_FILENAME, "")
    path = buildPath(user.account.fileRoot, dir, name)
    if not os.path.exists(path):
        raise HLException("Specified file or directory does not exist.")
    if os.path.isdir(path):
        if not user.has_perm(PERM_DELETE_FOLDERS):
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
        if not user.has_perm(PERM_DELETE_FILES):
            raise HLException("You are not allowed to delete files.")
        file = HLFile(path)
        file.delete()
    server.send_packet(packet.response(), user)


@packet_handler(HTLC_HDR_FILE_MKDIR)
@require_permission(PERM_CREATE_FOLDERS, "create folders")
def handleFolderCreate(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    name = packet.string(DATA_FILENAME, "")
    path = buildPath(user.account.fileRoot, dir, name)
    if os.path.exists(path):
        raise HLException("Specified directory already exists.")
    os.mkdir(path, conf.DIR_UMASK)
    server.send_packet(packet.response(), user)


@packet_handler(HTLC_HDR_FILE_MOVE)
@require_permission(PERM_MOVE_FILES, "move files")
def handleFileMove(server, user, packet):
    oldDir = parseDir(packet.binary(DATA_DIR))
    newDir = parseDir(packet.binary(DATA_NEWDIR))
    name = packet.string(DATA_FILENAME, "")

    oldPath = buildPath(user.account.fileRoot, oldDir, name)
    newPath = buildPath(user.account.fileRoot, newDir, name)

    if not os.path.exists(oldPath):
        raise HLException("Invalid file or directory.")
    if os.path.exists(newPath):
        raise HLException("The specified file already exists in the new location.")

    file = HLFile(oldPath)
    file.rename(newPath)

    server.send_packet(packet.response(), user)


@packet_handler(HTLC_HDR_FILE_GETINFO)
def handleFileGetInfo(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    name = packet.string(DATA_FILENAME, b"")

    path = buildPath(user.account.fileRoot, dir, name)
    if not os.path.exists(path):
        raise HLException("No such file or directory.")

    file = HLFile(path)
    d = datetime.fromtimestamp(os.path.getmtime(path))

    info = packet.response()
    info.add_string(DATA_FILENAME, name)
    info.add_number(DATA_FILESIZE, file.size())
    info.add_number(DATA_FILETYPE, file.getType())
    info.add_number(DATA_FILECREATOR, file.getCreator())
    info.add(DATA_DATECREATED, HLEncodeDate(d))
    info.add(DATA_DATEMODIFIED, HLEncodeDate(d))
    info.add_string(DATA_COMMENT, file.getComment())
    server.send_packet(info, user)


@packet_handler(HTLC_HDR_FILE_SETINFO)
def handleFileSetInfo(server, user, packet):
    dir = parseDir(packet.binary(DATA_DIR))
    oldName = packet.string(DATA_FILENAME, "")
    newName = packet.string(DATA_NEWFILE, oldName)
    comment = packet.string(DATA_COMMENT, "")

    if (oldName != newName) and (not user.has_perm(PERM_RENAME_FILES)):
        raise HLException("You cannot rename files.")

    oldPath = buildPath(user.account.fileRoot, dir, oldName)
    newPath = buildPath(user.account.fileRoot, dir, newName)

    if not os.path.exists(oldPath):
        raise HLException("Invalid file or directory.")
    if (oldPath != newPath) and os.path.exists(newPath):
        raise HLException("The specified file already exists.")

    file = HLFile(oldPath)
    file.rename(newPath)
    file.setComment(comment)

    server.send_packet(packet.response(), user)
