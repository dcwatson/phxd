from phxd.server.database import HLDatabase
from phxd.types import *

import os


def instance(arg):
    return TextDatabase(arg)


class TextDatabase (HLDatabase):
    """ Text-based implementation of HLDatabase. """

    def __init__(self, arg):
        self.rootDir = arg
        self.newsDir = os.path.join(arg, "news")
        self.accountsFile = os.path.join(arg, "accounts")
        self.banlistFile = os.path.join(arg, "banlist")

    def isConfigured(self):
        return os.path.exists(self.rootDir) and os.path.exists(self.newsDir)

    def setup(self):
        if not os.path.exists(self.rootDir):
            os.mkdir(self.rootDir)
        if not os.path.exists(self.newsDir):
            os.mkdir(self.newsDir)

    def loadAccount(self, login):
        acct = None
        try:
            fp = file(self.accountsFile, "r")
        except IOError:
            return acct
        for l in fp.readlines():
            parts = l.rstrip("\n").split("\t")
            if parts[0] == login:
                acct = HLAccount(login)
                try:
                    (acct.password, acct.name, acct.privs, acct.fileRoot) = parts[1:5]
                    acct.privs = int(acct.privs)
                    break
                except:
                    return None
        fp.close()
        return acct

    def saveAccount(self, acct):
        try:
            fp = file(self.accountsFile, "r")
            lines = fp.readlines()
            fp.close()
        except IOError:
            lines = []
        updated = False
        acctLine = "%s\t%s\t%s\t%s\t%s\n" % (acct.login, acct.password, acct.name, acct.privs, acct.fileRoot)
        for k in range(len(lines)):
            parts = lines[k].rstrip().split("\t")
            if parts[0] == acct.login:
                lines[k] = acctLine
                updated = True
                break
        if not updated:
            lines.append(acctLine)
        fp = file(self.accountsFile, "w")
        fp.write("".join(lines))
        fp.close()

    def deleteAccount(self, login):
        try:
            fp = file(self.accountsFile, "r")
        except IOError:
            return False
        (found, lines) = (False, fp.readlines())
        fp.close()
        for k in range(len(lines)):
            if lines[k].split("\t")[0] == login:
                found = True
                del(lines[k])
                break
        if not found:
            return False
        fp = file(self.accountsFile, "w")
        fp.write("".join(lines))
        fp.close()
        return True

    def loadNewsPosts(self, limit=0, offset=0, search=None):
        posts = []
        files = sorted(os.listdir(self.newsDir), reverse=True)
        for f in files[offset:limit]:
            post = HLNewsPost()
            fp = file(os.path.join(self.newsDir, f), "r")
            (post.date, post.login, post.nick) = fp.readline().rstrip().split("\t")[0:3]
            post.body = "".join(fp.readlines())
            fp.close()
            posts.append(post)
        return (posts, len(files))

    def saveNewsPost(self, post):
        files = sorted(os.listdir(self.newsDir), reverse=True)
        new_id = 1
        if len(files) > 0:
            new_id = int(files[0]) + 1
        fname = "%05d" % new_id
        fp = file(os.path.join(self.newsDir, fname), "w")
        fp.write("%s\t%s\t%s\n%s" % (post.date, post.login, post.nick, post.body))
        fp.close()
