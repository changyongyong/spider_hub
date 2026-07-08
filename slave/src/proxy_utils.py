def proxy_label(proxy: dict[str, str] | None) -> str:
    if not proxy:
        return "direct"
    return proxy["server"]
