from phxd.server.config import conf
from phxd.types import HLException


def certifyIcon(data):
    if len(data) > conf.MAX_GIF_SIZE:
        raise HLException("GIF icon too large.")
        return False

    # try to make sure the icon data is a 232x18 pixel GIF
    try:
        import Image
        import StringIO
        im = Image.open(StringIO.StringIO(data))
        if im.format != 'GIF':
            raise HLException("Icon must be in GIF format.")
        if im.size != (232, 18):
            raise HLException("GIF icon must be 232x18 pixels.")
    except ImportError:
        pass
    except IOError:
        return False

    return True
