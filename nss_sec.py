#nSS -- Security modules

import nss

class GrepPathBarrier(nss.HTTPManager):
    def __init__(self, param=None):
        self.param=param
    def Handle(self, client, req, server):
        if self.param and self.param in req.path:
            #Stop the manager propagation chain with an error.
            raise nss.HTTPError(403, longdesc='Permission to path explicitly denied.')
        else:
            return None #Allow the next manager to take over