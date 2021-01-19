"""
Tornado-based proxy server for MLFlow and JupyterHub.

The open-source version of MLFlow doesn't currently offer authenticatioWe'd like to run it as a JupyterHub service anyway. So this library provides
a simple HTTP Proxy that delegates to JupyterHub for authentication.
"""
import logging
import os

from jupyterhub.services.auth import HubAuthenticated
from tornado import web, ioloop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPClientError

__version__ = "1.0.1"

if os.environ.get("JUPYTERHUB_API_TOKEN", None) is None:
    raise RuntimeError("set JUPYTERHUB_API_TOKEN")
JUPYTERHUB_MLFLOW_AUTH_TARGET = os.environ.get("JUPYTERHUB_MLFLOW_AUTH_TARGET")
if JUPYTERHUB_MLFLOW_AUTH_TARGET is None:
    raise RuntimeError("set JUPYTERHUB_MLFLOW_AUTH_TARGET")

JUPYTERHUB_MLFLOW_AUTH_PORT = int(os.environ.get("JUPYTERHUB_MLFLOW_AUTH_PORT", 8700))

logger = logging.getLogger("tornado")
logger.setLevel(logging.INFO)


class HubProxyHandler(HubAuthenticated, web.RequestHandler):
    def get_current_user(self):
        """
        Overrides HubAuthenticated.get_current_user to work with MLFLow.

        MLFLow clients really only support HTTP Basic auth and HTTP Bearer auth. This
        doesn't jive with JupyterHub's auth.

        Under the assumption that we can't change the MLFlow clients, we make do with
        Bearer auth. We'll configure *clients* to make requests with
        `Authorization: Bearer <JUPYTERHUB_API_TOKEN>`. Then our proxy will look for
        `Bearer` authentication, and substitute in `Authorization: token <JUPYTERHUB_API_TOKEN>`.
        """
        auth = self.request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            auth = "token %s" % auth.split(" ", 1)[1]
            self.request.headers["Authorization"] = auth
        return super().get_current_user()

    @web.authenticated
    async def get(self):
        await self.proxy_request(self.request, method="GET")

    @web.authenticated
    async def post(self):
        await self.proxy_request(self.request, method="POST")

    async def proxy_request(self, request, method):
        url = "http://" + JUPYTERHUB_MLFLOW_AUTH_TARGET + request.uri
        body = None if method == "GET" else self.request.body
        proxy_request = HTTPRequest(
            url, method=method, headers=request.headers, body=body
        )
        client = AsyncHTTPClient()

        try:
            resp = await client.fetch(proxy_request)
        except HTTPClientError as e:
            if e.code == 304:  # Not Modifed
                return self.finish()
            raise web.HTTPError(404)

        self.set_status(resp.code)
        for k, v in resp.headers.get_all():
            self.add_header(k, v)
        self.write(resp.body)
        # tornado tries to be smart with the `Content-Type` header based on
        # the type to `self.write`. We need to explicitly set it here.
        self.set_header("Content-Type", resp.headers.get("Content-Type"))


def main():
    application = web.Application(
        [
            (r"/.*", HubProxyHandler),
        ]
    )
    application.listen(JUPYTERHUB_MLFLOW_AUTH_PORT)
    logger.info("listening at %d", JUPYTERHUB_MLFLOW_AUTH_PORT)
    ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
