import dorm

from phxd.server import HLServer
from phxd.server.config import conf, default
from phxd.utils import import_string

import argparse
import asyncio
import importlib
import logging.config
import os
import sys


def init():
    print('Initializing PHXD server configs in {}'.format(os.getcwd()))
    if os.path.exists('config.py'):
        print('  - config.py (already exists)')
    else:
        default_config = open(default.__file__, 'r').read()
        with open('config.py', 'w') as new_config:
            new_config.write(default_config)
        print('  + config.py')
    for name in ('files', 'chatlogs'):
        os.makedirs(name, exist_ok=True)
        print('  + {}/'.format(name))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config", help="The configuration module to load.")
    parser.add_argument("command", nargs='?', choices=["init"])
    args = parser.parse_args()

    if args.command == 'init':
        return init()

    try:
        local_config = importlib.import_module(args.config)
        conf.update(local_config)
    except ImportError:
        pass

    logging.config.dictConfig(conf.LOGGING)

    dorm.setup(conf.DB_FILE, models='phxd.types')

    if sys.platform == 'win32':
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    server = HLServer(loop=loop)
    for handler_path in conf.HANDLERS:
        try:
            handler_class = import_string(handler_path)
            server.register(handler_class())
        except Exception as err:
            logging.warning('Unable to add handler "%s": %s', handler_path, err)
    server.start()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
