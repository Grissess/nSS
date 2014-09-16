#Some basic NSS managers

import nss

import cStringIO
import cgi

class AllDocuments(nss.HTTPManager):
    def __init__(self, param=None):
        self.param=param or 'alldocs.html'
        self.status=200
        self.doc=open(self.param, 'rb').read()
    def Handle(self, client, req, server):
        return nss.HTTPResponse(self.doc, self.status)
    def __repr__(self):
        return '<AllDocuments serving '+self.param+'>'
    def do_loaddoc(self, line):
        '''loaddoc <document>

Loads the document which this object serves.'''
        self.param=line
        self.doc=open(self.param, 'rb').read()
    def do_setstatus(self, line):
        '''setstatus <status>

Sets the HTTP response code sent when the document is delivered.'''        
        self.status=int(line)

class ShowFormData(nss.HTTPManager):
    def __init__(self, param=None):
        if param is None:
            self.prefix='/'
        else:
            self.prefix=param
    def Handle(self, client, req, server):
        if not req.path.startswith(self.prefix):
            return
        resp=cStringIO.StringIO()
        resp.write('<html><head><title>Form Data</title></head><body>')
        resp.write('<h1>Form Data</h1>')
        if isinstance(req.formdata, dict):
            resp.write('<p>Form data is in dict form:</p>')
            resp.write('<table><tr><th>Key</th><th>Value</th></tr>')
            for key, val in req.formdata.iteritems():
                resp.write('<tr><td>'+key+'</td><td>'+repr(val)+'</td></tr>')
            resp.write('</table>')
        elif isinstance(req.formdata, cgi.FieldStorage):
            resp.write('<p>Form data is a FieldStorage:</p>')
            resp.write('<table><tr><th>Key</th><th>Value</th></tr>')
            for key in req.formdata:
                val=req.formdata[key]
                resp.write('<tr><td>'+key+'</td><td>')
                if val.filename:
                    resp.write('<i>File</i>')
                else:
                    resp.write(repr(val))
                resp.write('</td></tr>')
            resp.write('</table>')
        elif isinstance(req.formdata, str):
            resp.write('<p>Form data is a str: '+repr(req.formdata)+'</p>')
        else:
            resp.write('<p>Form data is in some weird format (%s)</p>'%(str(type(req.formdata))))
        return nss.HTTPResponse(resp)
    def do_setprefix(self, line):
        '''setprefix <prefix>

Sets the prefix of the path to which this object may respond.'''
        self.prefix=line

class RootDocument(nss.HTTPManager):
    def __init__(self, param=None):
        self.param=param or 'rootdoc.html'
        self.doc=open(self.param, 'rb').read()
        print 'WARNING! This is DEPRECATED! Use nss_fs instead.'
    def Handle(self, client, req, server):
        if req.path=='/':
            return nss.HTTPResponse(self.doc)
    def __repr__(self):
        return '<RootDocument serving '+self.param+'>'
    def do_loaddoc(self, line):
        '''loaddoc <document>

Loads the document which this object serves.'''
        self.param=line
        self.doc=open(self.param, 'rb').read()

class BananaDocument(nss.HTTPManager):
    def __init__(self):
        self.doc=open('bananadoc.html', 'rb').read()
        print 'WARNING! This is DEPRECATED! Use nss_fs instead.'
    def Handle(self, client, req, server):
        if req.path=='/banana':
            raise nss.HTTPRedirectError('/banana/', req.ver_s)
        elif req.path=='/banana/':
            return nss.HTTPResponse(self.doc)