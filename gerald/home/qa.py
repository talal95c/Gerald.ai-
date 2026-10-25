from __future__ import annotations


def default_ask(*args, **kwargs):
    from gerald.library import ask

    return ask(*args, **kwargs)
