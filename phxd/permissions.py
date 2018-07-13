class PermissionGroup (object):

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = []

    def __len__(self):
        return len(self.children)

    def __getitem__(self, idx):
        return self.children[idx]

    def register(self, perm):
        self.children.append(perm)
        if self.parent is not None:
            self.parent.register(perm)


class Permission (object):

    def __init__(self, name, bit, group=None):
        self.name = name
        self.bit = bit
        self.mask = 1 << (63 - bit)
        if group is not None:
            group.register(self)

    def __repr__(self):
        return "<Permission '%s': bit=%s>" % (self.name, self.bit)

    def __int__(self):
        return int(self.mask)

    def __and__(self, other):
        if hasattr(other, 'mask'):
            return self.mask & other.mask
        return self.mask & int(other)
    __rand__ = __and__

    def __or__(self, other):
        if hasattr(other, 'mask'):
            return self.mask | other.mask
        return self.mask | int(other)
    __ror__ = __or__

    def __invert__(self):
        return ~self.mask


all_permissions = PermissionGroup('All Permissions')

file_permissions = PermissionGroup('Files', all_permissions)
chat_permissions = PermissionGroup('Chat', all_permissions)
account_permissions = PermissionGroup('Accounts', all_permissions)
news_permissions = PermissionGroup('News', all_permissions)
user_permissions = PermissionGroup('Users', all_permissions)

permission_groups = [
    file_permissions,
    chat_permissions,
    account_permissions,
    news_permissions,
    user_permissions,
]

PRIV_DELETE_FILES = Permission('Delete Files', 0, file_permissions)
PRIV_UPLOAD_FILES = Permission('Upload Files', 1, file_permissions)
PRIV_DOWNLOAD_FILES = Permission('Download Files', 2, file_permissions)
PRIV_RENAME_FILES = Permission('Rename Files', 3, file_permissions)
PRIV_MOVE_FILES = Permission('Move Files', 4, file_permissions)
PRIV_CREATE_FOLDERS = Permission('Create Folders', 5, file_permissions)
PRIV_DELETE_FOLDERS = Permission('Delete Folders', 6, file_permissions)
PRIV_RENAME_FOLDERS = Permission('Rename Folders', 7, file_permissions)
PRIV_MOVE_FOLDERS = Permission('Move Folders', 8, file_permissions)
PRIV_READ_CHAT = Permission('Read Chat', 9, chat_permissions)
PRIV_SEND_CHAT = Permission('Send Chat', 10, chat_permissions)
PRIV_CREATE_CHATS = Permission('Create Private Chats', 11, chat_permissions)
PRIV_DELETE_CHATS = Permission('Delete Private Chats', 12, chat_permissions)
PRIV_SHOW_USER = Permission('Show In Userlist', 13, user_permissions)
PRIV_CREATE_USERS = Permission('Create Accounts', 14, account_permissions)
PRIV_DELETE_USERS = Permission('Delete Accounts', 15, account_permissions)
PRIV_READ_USERS = Permission('Read Accounts', 16, account_permissions)
PRIV_MODIFY_USERS = Permission('Modify Accounts', 17, account_permissions)
PRIV_CHANGE_PASSWORD = Permission('Change Own Password', 18, account_permissions)
PRIV_READ_NEWS = Permission('Read News', 20, news_permissions)
PRIV_POST_NEWS = Permission('Post News', 21, news_permissions)
PRIV_KICK_USERS = Permission('Kick Users', 22, user_permissions)
PRIV_KICK_PROTECT = Permission('Cannot Be Disconnected', 23, user_permissions)
PRIV_USER_INFO = Permission('View User Information', 24, user_permissions)
PRIV_UPLOAD_ANYWHERE = Permission('Upload Anywhere', 25, file_permissions)
PRIV_USE_ANY_NAME = Permission('Can Use Any Name', 26, user_permissions)
PRIV_NO_AGREEMENT = Permission('Show Agreement', 27, user_permissions)
PRIV_COMMENT_FILES = Permission('Comment Files', 28, file_permissions)
PRIV_COMMENT_FOLDERS = Permission('Comment Folders', 29, file_permissions)
PRIV_VIEW_DROPBOXES = Permission('View Dropboxes', 30, file_permissions)
PRIV_MAKE_ALIASES = Permission('Make Aliases', 31, file_permissions)
PRIV_BROADCAST = Permission('Broadcast', 32, user_permissions)
PRIV_SEND_MESSAGES = Permission('Send Messages', 40, user_permissions)
