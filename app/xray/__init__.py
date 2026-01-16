from random import randint
from typing import TYPE_CHECKING, Dict, Sequence

from app.models.proxy import ProxyHostSecurity
from app.utils.store import DictStorage
from app.utils.system import check_port
from app.xray import operations
from app.xray.config import XRayConfig
from app.xray.core import XRayCore
from app.xray.node import XRayNode
from config import XRAY_ASSETS_PATH, XRAY_EXECUTABLE_PATH, XRAY_JSON, XRAY_OVERRIDE_API
from xray_api import XRay as XRayAPI
from xray_api import exceptions, types
from xray_api import exceptions as exc

core = XRayCore(XRAY_EXECUTABLE_PATH, XRAY_ASSETS_PATH)

# Search for a free API port
found_port = None
try:
    for api_port in range(randint(10000, 60000), 65536):
        if not check_port(api_port):
            found_port = api_port
            break
    if found_port is None:
        raise RuntimeError("no free API port found")
finally:
    if XRAY_OVERRIDE_API:
        api_host, api_port = XRAY_OVERRIDE_API.split(":")
        config = XRayConfig(XRAY_JSON, api_port=api_port, api_host=api_host)
    else:
        config = XRayConfig(XRAY_JSON, api_port=found_port)
    # no need for del
api = XRayAPI(config.api_host, config.api_port)

nodes: Dict[int, XRayNode] = {}


if TYPE_CHECKING:
    from app.db.models import ProxyHost


@DictStorage
def hosts(storage: dict):
    from app.db import GetDB, crud

    storage.clear()
    with GetDB() as db:
        for inbound_tag in config.inbounds_by_tag:
            inbound_hosts: Sequence[ProxyHost] = crud.get_hosts(db, inbound_tag)

            storage[inbound_tag] = [
                {
                    "remark": host.remark,
                    "address": [i.strip() for i in host.address.split(",")]
                    if host.address
                    else [],
                    "port": host.port,
                    "path": host.path if host.path else None,
                    "sni": [i.strip() for i in host.sni.split(",")] if host.sni else [],
                    "host": [i.strip() for i in host.host.split(",")]
                    if host.host
                    else [],
                    "alpn": host.alpn.value,
                    "fingerprint": host.fingerprint.value,
                    # None means the tls is not specified by host itself and
                    #  complies with its inbound's settings.
                    "tls": None
                    if host.security == ProxyHostSecurity.inbound_default
                    else host.security.value,
                    "allowinsecure": host.allowinsecure,
                    "mux_enable": host.mux_enable,
                    "fragment_setting": host.fragment_setting,
                    "noise_setting": host.noise_setting,
                    "random_user_agent": host.random_user_agent,
                    "use_sni_as_host": host.use_sni_as_host,
                }
                for host in inbound_hosts
                if not host.is_disabled
            ]


__all__ = [
    "config",
    "hosts",
    "core",
    "api",
    "nodes",
    "operations",
    "exceptions",
    "exc",
    "types",
    "XRayConfig",
    "XRayCore",
    "XRayNode",
]
