#nSS Introspection managers
#MUST be imported by nss

import nss
import cStringIO
import cgi

class ShowManagers(nss.HTTPManager):
    def __init__(self, param=None):
        self.prefix=param
        if not self.prefix:
            self.prefix='/'
    def Handle(self, client, req):
        if not req.path.startswith(self.prefix):
            return
        resp=cStringIO.StringIO()
        hdrs={}
        if 'xml' in req.formdata:
            resp.write('<managers>')
            for man in nss.HTTPHandler.GetManagers():
                resp.write('<manager name="'+cgi.escape(repr(man))+'" enabled="'+('1' if getattr(man, 'enabled', True) else '0')+'"/>')
            resp.write('</managers>')
            hdrs['Content-type']='application/xml'
        else:
            resp.write('<html><head><title>All Managers</title></head><body>')
            resp.write('<p>All Managers:</p>')
            resp.write('<table><tr><th>Representation</th><th>Enabled</th></tr>')
            for man in nss.HTTPHandler.GetManagers():
                resp.write('<tr><td>'+cgi.escape(repr(man))+'</td>')
                if getattr(man, 'enabled', True):
                    resp.write('<td style="color:#00FF00;">Enabled</td>')
                else:
                    resp.write('<td style="color:#FF0000;">Disabled</td>')
                resp.write('</tr>')
            resp.write('</table></body></html>')
        return nss.HTTPResponse(resp, headers=hdrs)
    def do_setprefix(self, line):
        '''setprefix <line>

Sets the prefix with which to filter the path for this object to activate.'''
        self.prefix=line