from .base import *  # noqa: F403


if ENVIRONMENT == "dev":  # noqa: F405
    from .dev import *  # noqa: F403
elif ENVIRONMENT == "stg":  # noqa: F405
    from .stg import *  # noqa: F403
elif ENVIRONMENT == "prod":  # noqa: F405
    from .prod import *  # noqa: F403
else:
    raise ValueError(
        f"Unsupported ENVIRONMENT {ENVIRONMENT!r}. Use one of: dev, stg, prod."  # noqa: F405
    )
