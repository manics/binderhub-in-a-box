"""
Override the external access URL for JupyterHub by setting the
environment variable JUPYTERHUB_EXTERNAL_URL
"""
import argparse
import asyncio
import os
import socket
import sys
from argparse import ArgumentParser

import binderhub.app
import jupyterhub.app
from binderhub.binderspawner_mixin import BinderSpawnerMixin
from binderhub.build_local import LocalRepo2dockerBuild
from dockerspawner import DockerSpawner
from tornado.ioloop import IOLoop
from traitlets import Bool
from traitlets import Unicode


# image & token are set via spawn options
class LocalContainerSpawner(BinderSpawnerMixin, DockerSpawner):
    cmd = Unicode("jupyter-notebook")
    debug = Bool(True)
    remove = Bool(True)


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
hostip = s.getsockname()[0]
s.close()


def run_jupyterhub(engine):
    binderhub_service_name = "binder"

    config = dict(
        spawner_class=LocalContainerSpawner,
        log_level="DEBUG",
        authenticator_class="nullauthenticator.NullAuthenticator",
        hub_ip="0.0.0.0",
        hub_connect_ip=hostip,
        services=[
            {
                "name": binderhub_service_name,
                "admin": True,
                "command": [sys.executable, __file__, "--binderhub"],
                "url": "http://localhost:8585",
                "environment": {
                    "JUPYTERHUB_EXTERNAL_URL": os.getenv("JUPYTERHUB_EXTERNAL_URL", "")
                },
            }
        ],
        default_url=f"/services/{binderhub_service_name}/",
        # tornado_settings={
        #     "slow_spawn_timeout": 0,
        # },
    )

    app = jupyterhub.app.JupyterHub(**config)

    async def launch_instance_async(app):
        try:
            await app.initialize()
            await app.start()
        except Exception:
            app.log.exception("")
            app.exit(1)

    loop = IOLoop.current()
    task = asyncio.ensure_future(launch_instance_async(app))
    try:
        loop.start()
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        if task.done():
            # re-raise exceptions in launch_instance_async
            task.result()
        loop.stop()
        loop.close()


def run_binderhub(engine):
    # Assert that we're running as a managed JupyterHub service
    # (otherwise hub_api_token is needed)
    assert os.getenv("JUPYTERHUB_API_TOKEN")
    config = dict(
        debug=True,
        use_registry=False,
        builder_required=False,
        build_class=LocalRepo2dockerBuild,
        push_secret=None,
        about_message="BinderHub-in-a-Box",
        banner_message='See <a href="https://github.com/jupyterhub/binderhub">'
        "BinderHub on GitHub</a>",
        hub_url_local="http://localhost:8000",
        base_url=os.getenv("JUPYTERHUB_SERVICE_PREFIX", "/"),
        # JUPYTERHUB_BASE_URL may not include the host
        # hub_url=os.getenv('JUPYTERHUB_BASE_URL'),
        hub_url=os.getenv("JUPYTERHUB_EXTERNAL_URL") or f"http://{hostip}:8000",
    )

    app = binderhub.app.BinderHub(**config)
    app.initialize()
    app.start()


if __name__ == "__main__":
    parser = ArgumentParser("binderhub-in-a-box")
    parser.add_argument(
        "--engine",
        default="docker",
        choices=["docker"],
        # choices=["docker", "podman"],
        help="Container runtime",
    )
    parser.add_argument("--binderhub", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.binderhub:
        sys.argv = ["binderhub"]
        run_binderhub(args.engine)
    else:
        sys.argv = ["jupyterhub"]
        run_jupyterhub(args.engine)
