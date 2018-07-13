from phxd.server.config import default as default_settings


class Settings:
    def __init__(self):
        self._vars = {}
        self.update(default_settings)

    def __getattr__(self, name):
        return self._vars[name]

    def update(self, mod):
        for name in dir(mod):
            if not name.startswith('_'):
                self._vars[name] = getattr(mod, name)


conf = Settings()
