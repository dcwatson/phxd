from phxd.server.config import default as default_settings

import importlib


class Settings:
    def __init__(self):
        self._vars = {}
        self.update(default_settings)

    def __getattr__(self, name):
        return self._vars[name]

    def update(self, mod):
        if isinstance(mod, str):
            mod = importlib.import_module(mod)
        for name in dir(mod):
            if name.isupper() and not name.startswith('_'):
                self._vars[name] = getattr(mod, name)


conf = Settings()
