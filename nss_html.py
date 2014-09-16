#neXus Service Software HTML stuff

import nss

class HTMLInjector(nss.HTTPModifier):
    def __init__(self, param=None):
        if not param:
            param='/,overlay.html,0'
        prefix, fname, useerror=param.split(',')
        self.prefix=prefix
        self.fname=fname
        self.useerror=bool(int(useerror))
        self.doc=open(fname, 'rb').read()
    def Handle(self, client, req, resp, creator, fromerror, server):
        if not req.path.startswith(self.prefix):
            return
        if isinstance(resp, nss.HTTPRawResponse):
            #We're gonna wing it. See if there's a line like this:
            if 'content-type: text/html' not in resp.read(1024).lower():
                return
            #if so...
            buf=resp.payload.getvalue()
            inj=buf.rfind('</body>')
            buf=buf[:inj]+self.doc+buf[inj:]
            #Strip off the headers and turn into a bona-fide Response
            #for speedy delivery
            if '\r\n\r\n' in buf[:1024]:
                return nss.HTTPResponse(buf[buf.index('\r\n\r\n')+4:])
            return nss.HTTPResponse(buf[buf.index('\n\n')+2:])
        elif isinstance(resp, nss.HTTPResponse):
            if not resp.headers['Content-type'].lower()=='text/html':
                return
            if (not self.useerror) and fromerror:
                return
            buf=resp.payload.getvalue()
            inj=buf.rfind('</body>')
            buf=buf[:inj]+self.doc+buf[inj:]
            return nss.HTTPResponse(buf)
        return