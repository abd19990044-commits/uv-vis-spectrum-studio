from __future__ import annotations

from . import __version__
from . import main_app

main_app.APP_VERSION = __version__
main_app.run()
