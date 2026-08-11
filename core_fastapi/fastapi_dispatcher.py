from io import BytesIO
from odoo.addons.fastapi.fastapi_dispatcher import FastApiDispatcher


class ContactApiFastApiDispatcher(FastApiDispatcher):

    def dispatch(self, endpoint, args):
        """
        Overwrite to update the root_path calculation method in fastapi module
        """
        # don't parse the httprequest let starlette parse the stream
        self.request.params = {}  # dict(self.request.get_http_params(), **args)
        environ = self._get_environ()
        root_path = "/".join(environ["PATH_INFO"].split("/")[:3])  # root_path: /api/v*
        # depends method
        fastapi_endpoint = self.request.env["fastapi.endpoint"].sudo()
        app = fastapi_endpoint.get_app(root_path)
        uid = fastapi_endpoint.get_uid(root_path)
        data = BytesIO()
        
        with self._manage_odoo_env(uid):
            for r in app(environ, self._make_response):
                data.write(r)
            if self.inner_exception:
                raise self.inner_exception
            return self.request.make_response(
                data.getvalue(), headers=self.headers, status=self.status
            )

    def _make_response(self, status_mapping, headers_tuple, content):
        super()._make_response(status_mapping, headers_tuple, content)
        self.status = status_mapping[:3]
        # set charset=utf-8 into content-type
        new_headers = [(k, v) if k.lower() != 'content-type' or 'charset' in v.lower()
                       else (k, v + '; charset=utf-8') for k, v in headers_tuple]
        self.headers = dict(new_headers)
