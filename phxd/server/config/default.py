import socket


################################################################################
# database configuration
################################################################################

DB_FILE = 'phxd.db'

################################################################################
# logging configuration
################################################################################

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'phxd': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

################################################################################
# server configuration
################################################################################

SERVER_BIND = '0.0.0.0'
SERVER_PORTS = (5500,)
SERVER_NAME = "my_phxd_server"
IDLE_TIME = 10 * 60
BAN_TIME = 15 * 60
HANDLERS = [
    'phxd.server.handlers.user.UserHandler',
    'phxd.server.handlers.chat.ChatHandler',
    'phxd.server.handlers.message.MessageHandler',
    'phxd.server.handlers.account.AccountHandler',
    'phxd.server.handlers.news.NewsHandler',
    'phxd.server.handlers.files.FilesHandler',
    'phxd.server.handlers.icon.IconHandler',
]

################################################################################
# SSL configuration
################################################################################

ENABLE_SSL = False
SSL_PORT = 5600
SSL_KEY_FILE = 'certs/privkey.pem'
SSL_CERT_FILE = 'certs/cacert.pem'

################################################################################
# tracker configuration
################################################################################

ENABLE_TRACKER_REGISTER = False
TRACKER_ADDRESS = "hltracker.com"
TRACKER_PORT = 5499
TRACKER_PASSWORD = ""
TRACKER_INTERVAL = 5 * 60
SERVER_DESCRIPTION = "My phxd server."

################################################################################
# chat options
################################################################################

# filled with (nick, chat)
CHAT_FORMAT = "\r%13.13s:  %s"
CHAT_PREFIX_LEN = 17
CHAT_PREFIX_ADD_NICK_LEN = False
EMOTE_FORMAT = "\r *** %s %s"
EMOTE_PREFIX_LEN = 7  # + len(nick)
MAX_NICK_LEN = 32
MAX_CHAT_LEN = 4096
LOG_CHAT = True
LOG_DIR = "chatlogs"

################################################################################
# message options
################################################################################

MAX_MSG_LEN = 2048

################################################################################
# news options
################################################################################

# filled with (nick, login, date, body)
NEWS_FORMAT = "From %s [%s] (%s):\r\r%s\r_________________________________________________________\r"
DEFAULT_NEWS_LIMIT = 25

################################################################################
# files options
################################################################################

FILE_ROOT = "files"
SHOW_DOTFILES = False
DIR_UMASK = 0o755
UPLOAD_SCRIPT = None

################################################################################
# transfer options
################################################################################

XFER_TIMEOUT = 30.0

################################################################################
# GIF icon options
################################################################################

ENABLE_GIF_ICONS = True
MAX_GIF_SIZE = 32768
DEFAULT_ICON_TIME = 10


################################################################################
# IRC server configuration
################################################################################

ENABLE_IRC = True
IRC_SERVER_NAME = socket.gethostname()
IRC_PORT = 6667
IRC_DEFAULT_ACCOUNT = 'guest'
IRC_DEFAULT_CHANNEL = '#phxd'
