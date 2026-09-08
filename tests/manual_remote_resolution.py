from sclpl.catalog.resolve import resolve
from sclpl.ext.resources import (
    ResourceCapabilities,
    ResourceInfo,
    clear_resource_providers,
    register_resource_provider,
)


class Provider:
    scheme = "memory"
    data = {"memory://jobs/orders/workflow.sclpll": b"@workflow orders\n"}

    def capabilities(self): return ResourceCapabilities()
    def normalize(self, uri): return uri
    def resolve(self, base, reference): return base + reference
    def stat(self, uri): return ResourceInfo(uri=uri)
    def exists(self, uri): return uri in self.data
    def list(self, uri): return []
    def download(self, uri, target): target.write(self.data[uri]); return ResourceInfo(uri=uri)
    def upload(self, source, uri, **kwargs): return ResourceInfo(uri=uri)
    def display_uri(self, uri): return uri


clear_resource_providers()
register_resource_provider("memory", Provider())
located = resolve("memory://jobs/orders/")
assert located.doc.name == "orders"
assert located.origin_uri == "memory://jobs/orders/workflow.sclpll"
print("remote-resolution-ok")
