#NSS File System managers

#TODO: GPSP Style Dirformatter

#TODO: Grep-style Manager for blocking named paths...mport nss

import mimetypes
mimetypes.init()
import os
import sys
import cStringIO
import subprocess

import nss #Duh

USE_404=False #If True, raises 404 if the prefix matches
#and the entry is not in localpath; if False, simply
#returns None and lets other managers continue.

class SimpleFileSystem(nss.HTTPManager):
    DIR_FORMATTER=None #Set later...
    DIR_OVERRIDES=('index.html', 'index.htm')
    DEFAULT_MIMETYPE='application/octet-stream'
    def __init__(self, param=None):
        if param is None:
            param='/,'+os.getcwd()
        #Param must represent a string of the form
        #prefix,localdir
        #(e.g. /fileroot/,C:\Server\FileRoot)
        #if no param is specified, serves / to the
        #current working directory.
        #An empty localpath, e.g. "/fileroot/,",
        #uses the cwd.
        #prefix MUST end in /. Otherwise clients
        #will gain access to the file system root.
        #This constructor corrects this, but you
        #should still know.
        prefix, sep, localpath=param.partition(',')
        if not localpath:
            localpath=os.getcwd()
        if not prefix.endswith('/'):
            prefix=prefix+'/'
        self.prefix=prefix
        self.localpath=localpath
    def Handle(self, client, req, server):
        if '.' not in req.path and not req.path.endswith('/'): #And thus we can safely assume it's a directory,
            raise nss.HTTPRedirectError(req.path+'/')
        if req.path.startswith(self.prefix):
            reqpath=req.path[len(self.prefix):]
            syspath=os.path.normpath(reqpath)
            fullpath=os.path.join(self.localpath, syspath)
            if not os.path.exists(fullpath):
                raise nss.HTTPError(404, longdesc='Entity does not exist.')
            if os.path.isdir(fullpath):
                #Check for directory overrides
                for oname in self.DIR_OVERRIDES:
                    ofull=os.path.join(fullpath, oname)
                    if os.path.exists(ofull) and os.path.isfile(ofull):
                        fullpath=ofull
                        break
                else: #No directory, do a listing
                    return self.DIR_FORMATTER.ListDir(fullpath, reqpath)
            contenttype=mimetypes.guess_type(fullpath, False)[0]
            if contenttype is None:
                contenttype=self.DEFAULT_MIMETYPE
            try:
                f=open(fullpath, 'rb')
            except (EnvironmentError, IOError):
                raise nss.HTTPError(403, longdesc='The server lacks access permissions to read this file.')
            return nss.HTTPResponse(f, contenttype=contenttype)
        if USE_404:
            raise nss.HTTPError(404, longdesc='File or directory not found.')
        else:
            return None
    def __repr__(self):
        return '<SimpleFileSystem mapping '+self.prefix+'->'+self.localpath+' using '+repr(self.DIR_FORMATTER)+'>'
    def do_setformat(self, line):
        '''setformat [<module> <class>]

Sets the formatter to <class> from <module>, reloading if necessary.
If no argument is specified, restores the default DirFormatter instance.
Throws ImportError if the module cannot be located, and AttributeError if the classname is not found.'''
        if not line.strip():
            self.DIR_FORMATTER=DirFormatter()
            return
        parts=line.split(' ')
        modname=parts[0]
        clname=parts[1]
        g=globals()
        if modname in g:
            g[modname]=reload(g[modname])
        else:
            g[modname]=__import__(modname)
        mod=g[modname]
        self.DIR_FORMATTER=getattr(mod, clname)()
    def do_setprefix(self, line):
        '''setprefix <prefix>

Sets the prefix which this object handles (the HTTP path).'''
        self.prefix=line
        if not self.prefix.endswith('/'):
            self.prefix+='/'
    def do_setlocal(self, line):
        '''setlocal <localpath>

Sets the local path which this object handles (the filesystem root).'''
        self.localpath=line

class DirFormatter(object):
    def ListDir(self, fullpath, disppath):
        try:
            ents=os.listdir(fullpath)
        except (EnvironmentError, IOError):
            raise nss.HTTPError(403, longdesc='The server lacks access permissions to list this directory.')
        resp=cStringIO.StringIO()
        resp.write('<html><head><title>Directory listing: ')
        resp.write(disppath)
        resp.write('</title></head><body><ul>')
        resp.write('<li><a href="..">..</a></li>')
        for ent in ents:
            if os.path.isdir(os.path.join(fullpath, ent)):
                ent=ent+'/'
            resp.write('<li><a href="'+ent+'">'+ent+'</a></li>')
        resp.write('</ul></body></html>')
        return nss.HTTPResponse(resp)
    def __repr__(self):
        return '<Basic DirFormatter>'

SimpleFileSystem.DIR_FORMATTER=DirFormatter()

class CGIFileSystem(SimpleFileSystem):
    EXTENSIONS=('.py', '.pyc', '.pyo')
    def Handle(self, client, req, server):
        if not req.path.startswith(self.prefix):
            if USE_404:
                raise nss.HTTPError(404, longdesc='File or directory not found.')
            return
        reqpath=req.path[len(self.prefix):]
        syspath=os.path.normpath(reqpath)
        fullpath=os.path.join(self.localpath, syspath)
        if not os.path.exists(fullpath):
            raise nss.HTTPError(404, longdesc='Entity does not exist.')
        if os.path.isdir(fullpath):
            raise nss.HTTPError(403, longdesc='May not perform directory listings of CGI filesystems.')
        part, ext=os.path.splitext(fullpath)
        if ext not in self.EXTENSIONS:
            raise nss.HTTPError(403, longdesc='Not a CGI executable')
        #Set up the environment...
        env={}
        env['REQUEST_METHOD']=req.method
        env['QUERY_STRING']=req.urn.query
        env['REMOTE_ADDR']=client.peer[0]
        if 'Content-type' in req.headers:
            env['CONTENT_TYPE']=req.headers['Content-type']
        else:
            env['CONTENT_TYPE']=''
        if 'Content-length' in req.headers:
            env['CONTENT_LENGTH']=req.headers['Content-length']
        else:
            env['CONTENT_LENGTH']=''
        if 'Cookie' in req.headers:
            env['HTTP_COOKIE']=req.headers['Cookie']
        else:
            env['HTTP_COOKIE']=''
        #Run the script
        return self.DoRun(fullpath, env, client, req)
    def DoRun(self, path, env, client, req):
        #This is more or less the Windows way to approach, but
        #this function can be rewritten for *nix if need be.
        fullenv=os.environ.copy()
        fullenv.update(env)
        env=fullenv
##        for k, v in env.iteritems():
##            print k, repr(v)
        p=subprocess.Popen([sys.executable, '-u', path],
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           env=env)
        stdout, stderr=p.communicate(req.payload or None)
        resp=nss.HTTPRawResponse(stdout)
        #This is a rather hackish way of ensuring that the Content-length header
        #is properly set. After all, many of the scripts for neXus and GPSP don't set
        #it and instead trust us with dealing with it. The old server closed the
        #connection, which sent a pretty clear message to the browser, but the
        #new keep-alive support necessitates this hack.
        #Hopefully one day the scripts will be able to do this on their own. That will
        #make our job easier.
        http, sep, headers=resp.payload.getvalue().partition('\n')
        em=nss.PARSER.parsestr(headers, True)
        if 'Content-length' not in em:
            em['Content-length']=str(len(em.get_payload()))
            resp.payload=cStringIO.StringIO(http+sep+em.as_string())
        print stderr
        p.stderr.close()
        p.stdout.close()
        code=p.returncode
        print 'Process exit: returned', code, hex(code&0xffffffff)
        return resp