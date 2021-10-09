#!/usr/bin/env python
"""
Override the external access URL for JupyterHub by setting the
environment variable JUPYTERHUB_EXTERNAL_URL
"""
import argparse
import asyncio
import os
import socket
import subprocess
import sys

import binderhub.app
import docker
import jupyterhub.app
from binderhub.binderspawner_mixin import BinderSpawnerMixin
from binderhub.build_local import LocalRepo2dockerBuild
from binderhub.registry import FakeRegistry
from dockerspawner import DockerSpawner
from podmanclispawner import PodmanCLISpawner
from tornado.ioloop import IOLoop


class LocalContainerDockerSpawner(BinderSpawnerMixin, DockerSpawner):
    cmd = ["jupyter-notebook"]
    debug = True
    remove = True


class LocalContainerPodmanSpawner(BinderSpawnerMixin, PodmanCLISpawner):
    cmd = ["jupyter-notebook"]
    debug = True
    remove = True


class LocalRepo2dockerPodmanBuild(LocalRepo2dockerBuild):
    def get_r2d_cmd_options(self):
        return super().get_r2d_cmd_options() + [
            "--engine",
            "podman",
        ]


class LocalPodmanRegistry(FakeRegistry):
    async def get_image_manifest(self, image, tag):
        cmd = ["podman", "image", "exists", f"{image}:{tag}"]
        print(" ".join(cmd))
        r = subprocess.call(cmd)
        if r == 0:
            return {"image": image, "tag": tag}
        return None


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
hostip = s.getsockname()[0]
s.close()


def get_engine(engine):
    if engine != "auto":
        return engine
    try:
        docker.from_env(version="auto")
        return "docker"
    except docker.errors.DockerException:
        pass
    try:
        subprocess.check_output(["podman", "version"])
        return "podman"
    except Exception:
        pass

    raise ValueError(
        "Could not detect container engine, please use the `--engine` argument"
    )


def run_jupyterhub(engine):
    binderhub_service_name = "binder"

    config = dict(
        spawner_class=LocalContainerDockerSpawner,
        log_level="DEBUG",
        authenticator_class="null",
        hub_ip="0.0.0.0",
        hub_connect_ip=hostip,
        services=[
            {
                "name": binderhub_service_name,
                "admin": True,
                "command": [
                    sys.executable,
                    __file__,
                    "--binderhub",
                    f"--engine={engine}",
                ],
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

    if engine == "podman":
        config["spawner_class"] = LocalContainerPodmanSpawner

    app = jupyterhub.app.JupyterHub(**config)

    # The rest of this method is copied from
    # https://github.com/jupyterhub/jupyterhub/blob/2.0.0b2/jupyterhub/app.py#L3203-L3226
    # (I have no idea what I'm doing)

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
        base_url=os.environ["JUPYTERHUB_SERVICE_PREFIX"],
        # JUPYTERHUB_BASE_URL may not include the host but that should be OK
        hub_url=os.getenv("JUPYTERHUB_EXTERNAL_URL")
        or os.environ["JUPYTERHUB_BASE_URL"],
    )

    if engine == "podman":
        config["use_registry"] = True
        config["registry_class"] = LocalPodmanRegistry
        config["image_prefix"] = "localhost/"
        config["build_class"] = LocalRepo2dockerPodmanBuild

    app = binderhub.app.BinderHub(**config)
    app.initialize()
    app.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser("binderhub-in-a-box")
    parser.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "docker", "podman"],
        help="Container runtime",
    )
    # This is a hidden argument so we can run BinderHub as a JupyterHub service
    # without needing another executable script
    parser.add_argument("--binderhub", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    engine = get_engine(args.engine)
    # Overwrite sys.argv, otherwise JupyterHub/BinderHub try to parse arguments
    if args.binderhub:
        sys.argv = ["binderhub"]
        run_binderhub(engine)
    else:
        sys.argv = ["jupyterhub"]
        run_jupyterhub(engine)
