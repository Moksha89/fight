import os

ENV = os.environ.get("DJANGO_ENV", "dev")

if ENV == "prod":
    from .prodConfig import *  # noqa: F401, F403
else:
    from .devConfig import *  # noqa: F401, F403
