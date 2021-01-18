# MLFLow JupyterHub Auth

Tornado-based proxy server for MLFlow and JupyterHub.

The open-source version of MLFlow doesn't currently offer authentication.
We'd like to run it as a JupyterHub service anyway. So this library provides
a simple HTTP Proxy that delegates to JupyterHub for authentication.

## Configuration

The following environment variables should be set:

1. `JUPYTERHUB_API_TOKEN`: The API token for JupyterHub.
2. `JUPYTERHUB_MLFLOW_AUTH_TARGET`: The target URI where MLFLow is running.
3. `JUPYTERHUB_MLFLOW_AUTH_PORT`: The port that this tornado server should listen on. JupyterHub should look for the service on this port (default `8700`).

Given a `jupyterhub_config.py` with an MLFlow service like:

```python
# file: jupyterhub_config.py
import os
from traitlets import config

c = config.get_config()

# Register the MLFlow service with JupyterHub
c.JupyterHub.services = [
    {
        "name": "mlflow",
        "admin": True,
        "url": "http://127.0.0.1:8700",  # this port should match below.
        "api_token": "<JUPYTERHUB_API_TOKEN>"
    }
]
c.JupyterHub.service_tokens = {"<JUPYTERHUB_API_TOKEN>": "mlflow"}

c.JupyterHub.admin_access = True  # Service needs to access user servers.
c.JupyterHub.authenticator_class = 'jupyterhub.auth.DummyAuthenticator'

c.JupyterHub.spawner_class = "jupyterhub.spawner.SimpleLocalProcessSpawner"
c.SimpleLocalProcessSpawner.home_dir_template = os.getcwd()
```

We'll need to start the three servers. In this example we have

1. `mlflow` on port 5000 with the static prefix `/services/mlflow`
2. `mlflow_jupyterhub_auth` on the default port (`8700`)
3. `mlflow`

```console
$mlflow server --static-prefix=/services/mlflow
[2021-01-18 13:43:36 -0600] [32564] [INFO] Starting gunicorn 20.0.4
[2021-01-18 13:43:36 -0600] [32564] [INFO] Listening at: http://127.0.0.1:5000 (32564)
[2021-01-18 13:43:36 -0600] [32564] [INFO] Using worker: sync
```

2. MLFlow JupyterHub Auth

```console
$ JUPYTERHUB_MLFLOW_AUTH_TARGET="127.0.0.1:5000" JUPYTERHUB_API_TOKEN=<JUPYTERHUB_API_TOKEN> jupyterhub-mlflow-auth
```

3. JupyterHub

```console
$ jupyterhub --config=jupyterhub_config.py 
```
The console output for jupyterhub should include adding a service for jupyterhub-mlflow-auth at 8700, which will proxy requests to the MLFLow server at 127.0.0.1:5000 after authenticating.

Accessing the MLFlow service at, e.g. `http://localhost:8000/services/mlflow/#/` should now prompt for authentication before redirecting to MLFlow.