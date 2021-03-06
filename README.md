# BinderHub in a Box

**⚠️⚠️⚠️⚠️⚠️ Under development ⚠️⚠️⚠️⚠️⚠️**

An all-in-one opinionated package for running BinderHub and JupyterHub locally with minimal faff, using either Docker or Podman.

## Installation

Using [Conda](https://github.com/conda-forge/miniforge):

```sh
conda create -n binderhub-in-a-box -f environment.yml
```

Alternative using Pip and NPM:

```sh
pip install -r requirements.txt
npm install -g configurable-http-proxy
```

## Running binderhub-in-a-box

You must have either Docker or Podman on your system. Run:

```
python binderhub-in-a-box.py
```

If your container engine is not detected add `--engine docker` or `--engine podman`.

Go to http://localhost:8000/ and you should be redirected to BinderHub.
