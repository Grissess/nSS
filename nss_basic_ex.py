#nSS Extended Introspection

import cStringIO
import cgi

import nss

class ShowMounts(nss.HTTPManager):
    def Handle(self, client, req, server):
        resp=cStringIO.StringIO()
        resp.write('<html><body><h1>nSS Server Mounts:</h1>\n')
        for vserv in nss.PRIMARY_VSERVERS:
            resp.write('<h3>'+vserv.hname+'</h3>\n<table>')
            for pth in vserv.IterPaths():
                resp.write('<tr><td>'+str(pth)+'</td>')
                man=vserv.mounts[str(pth)]
                resp.write('<td>'+cgi.escape(repr(man))+'</td>')
                resp.write('<td style="color: %s">%s</td>'%(('green', 'Enabled') if getattr(man, 'enabled', True) else ('red', 'Disabled')))
                resp.write('</tr>')
            resp.write('</table>\n')
        resp.write('</body></html>')
        return nss.HTTPResponse(resp)
    def __repr__(self):
        return '<ShowMounts>'

class AllDocuments(nss.HTTPManager):
    def __init__(self, param=None):
        if param is None:
            param='alldocs.html'
        self.fname=param
        self.status=200
    def Handle(self, client, req, server):
        return nss.HTTPResponse(open(self.fname, 'rb'), self.status)
    def do_loaddoc(self, line):
        '''loaddoc <docname>

Sets the file served by this HTTPManager.'''
        self.fname=line
    def do_setstatus(self, line):
        '''setstatus <num>

Sets the HTTP status returned when this document is served.'''
        self.status=int(line)
    def __repr__(self):
        return '<AllDocuments serving '+self.fname+':'+str(self.status)+'>'
        
class Redirector(nss.HTTPManager):
    def __init__(self, param=None):
        if param is None:
            param='/'
        self.redirect=param
    def Handle(self, client, req, server):
        raise nss.HTTPRedirectError(self.redirect)
