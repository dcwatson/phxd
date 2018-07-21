import logging
import sys


__all__ = [
    "account",
    "chat",
    "files",
    "icon",
    "logger",
    "message",
    "news",
    "user",
]


def install(mod_base, mod_name):
    mod_path = ".".join([mod_base, mod_name])
    if mod_path not in sys.modules:
        mod = __import__(mod_path, None, None, mod_base)
        logging.debug("installing handler: %s", mod_path)
        if hasattr(mod, "install") and callable(mod.install):
            mod.install()


def uninstall(mod_base, mod_name):
    mod_path = ".".join([mod_base, mod_name])
    if mod_path in sys.modules:
        logging.debug("uninstalling handler: %s", mod_path)
        mod = sys.modules[mod_path]
        if hasattr(mod, "uninstall") and callable(mod.uninstall):
            mod.uninstall()
        del sys.modules[mod_path]


def reload(mod_base, mod_name):
    uninstall(mod_base, mod_name)
    install(mod_base, mod_name)


def install_all():
    for mod_name in __all__:
        install("phxd.server.handlers", mod_name)


def uninstall_all():
    for mod_name in __all__:
        uninstall("phxd.server.handlers", mod_name)


def reload_all():
    for mod_name in __all__:
        reload("phxd.server.handlers", mod_name)
