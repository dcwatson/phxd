from pydispatch import dispatcher

import logging
import sys


__all__ = [
    "chat",
    "user",
    "account",
    "news",
    "message",
    "icon",
    "files",
    "logger",
]


def install(mod_base, mod_name):
    mod_path = ".".join([mod_base, mod_name])
    if mod_path not in sys.modules:
        mod = __import__(mod_path, None, None, "phxd.server.handlers")
        logging.debug("installing handler: %s", mod_path)
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and hasattr(obj, "_signal_type"):
                dispatcher.connect(obj, signal=obj._signal_type)
        if hasattr(mod, "install") and callable(mod.install):
            mod.install()


def uninstall(mod_base, mod_name):
    mod_path = ".".join([mod_base, mod_name])
    if mod_path in sys.modules:
        logging.debug("uninstalling handler: %s", mod_path)
        mod = sys.modules[mod_path]
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and hasattr(obj, "_signal_type"):
                dispatcher.disconnect(obj, signal=obj._signal_type)
        if hasattr(mod, "uninstall") and callable(mod.uninstall):
            mod.uninstall()
        del sys.modules[mod_path]


def reload(mod_base, mod_name):
    uninstall(mod_base, mod_name)
    install(mod_base, mod_name)

# Methods for all "base" handlers


def install_all():
    for mod_name in __all__:
        install("phxd.server.handlers", mod_name)


def uninstall_all():
    for mod_name in __all__:
        uninstall("phxd.server.handlers", mod_name)


def reload_all():
    for mod_name in __all__:
        reload("phxd.server.handlers", mod_name)
