#NSS File System managers

#TODO: GPSP Style Dirformatter

#TODO: Grep-style Manager for blocking named paths...

import mimetypes
mimetypes.init()
import os
import sys
import cStringIO
import subprocess
import time
import tempfile

import nss #Duh

USE_404=False #If True, raises 404 if the prefix matches
#and the entry is not in localpath; if False, simply
#returns None and lets other managers continue.

class SimpleFileSystem(nss.HTTPManager):
    DIR_FORMATTER=None #Set later...
    DIR_OVERRIDES=('index.html', 'index.htm')
    DEFAULT_MIMETYPE='application/octet-stream'
    USE_404=USE_404
    def __init__(self, param=None):
        if param is None:
            param=os.getcwd()
        self.localpath=param
    def Handle(self, client, req, server):
        if '.' not in str(req.path) and not str(req.path).endswith('/'): #And thus we can safely assume it's a directory,
            raise nss.HTTPRedirectError(str(req.path)+'/')
        reqpath=str(req.localpath)
        syspath=os.path.normpath(reqpath)[1:]
        print 'IN SIMPLEFILESYSTEM: syspath is', syspath
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
        if self.USE_404:
            raise nss.HTTPError(404, longdesc='File or directory not found.')
        else:
            return None
    def __repr__(self):
        return '<'+self.__class__.__name__+' serving '+self.localpath+' using '+repr(self.DIR_FORMATTER)+'>'
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

class GPSPDirFormatter(DirFormatter):
    def ListDir(self, fullpath, disppath):
        try:
            ents=os.listdir(fullpath)
        except (EnvironmentError, IOError):
            raise nss.HTTPError(403, longdesc='The server lacks access permissions to list this directory.')
        resp=cStringIO.StringIO()
        resp.write('<html><head><title>Directory listing: ')
        resp.write(disppath)
        resp.write('</title></head><body><h1>Directory contents of <a href="/cgi/main.py">/</a>')
        parts=nss.Path.Make(disppath).Components
        for idx, part in enumerate(parts):
            if idx!=len(parts)-1:
                resp.write('<a href="/')
                resp.write('/'.join([i for j, i in enumerate(parts) if j<=idx]))
                resp.write('">')
                resp.write(part)
                resp.write('</a>')
        resp.write('<hr/>Directores:<hr/>')
        for ent in ents:
            if os.path.isdir(os.path.join(fullpath, ent)):
                resp.write('<a href="'+disppath+'/'+ent+'">'+ent+'</a>')
        resp.write('<hr/>Files:<hr/>')
        for ent in ents:
            if os.path.isfile(os.path.join(fullpath, ent)):
                resp.write('<a href="'+disppath+'/'+ent+'">'+ent+'</a>')

SimpleFileSystem.DIR_FORMATTER=DirFormatter()

class CGIFileSystem(SimpleFileSystem):
    #tuple of extensions -> (command to run, list of arguments to include before executable, boolean: send status code?)
    EXTENSIONS={('.py', '.pyc', '.pyo'): (sys.executable, ['-u'], False),
                ('.sh',): ('bash', [], True)}
    DEFAULT_STATUSCODE='HTTP/1.1 200 OK\n' #The status code sent for send status code==True
    def Handle(self, client, req, server):
        reqpath=str(req.localpath)
        syspath=os.path.normpath(reqpath)[1:]
        fullpath=os.path.join(self.localpath, syspath)
        if not os.path.exists(fullpath):
            raise nss.HTTPError(404, longdesc='Entity does not exist.')
        if os.path.isdir(fullpath):
            raise nss.HTTPError(403, longdesc='May not perform directory listings of CGI filesystems.')
        part, ext=os.path.splitext(fullpath)
        for extset, info in self.EXTENSIONS.iteritems():
            if ext in extset:
                executable, args, scode=info
                break
        else:
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
        return self.DoRun(fullpath, env, client, req, executable, args, scode)
    def DoRun(self, path, env, client, req, executable, args, scode):
        #This is more or less the Windows way to approach, but
        #this function can be rewritten for *nix if need be.
        fullenv=os.environ.copy()
        fullenv.update(env)
        env=fullenv
##        for k, v in env.iteritems():
##            print k, repr(v)
        print 'CGI: Preparing temporary files...'
        fstdin=tempfile.TemporaryFile()
        fstdout=tempfile.TemporaryFile()
        fstderr=tempfile.TemporaryFile()
        print 'CGI: Writing payload to fstdin...'
        fstdin.write(req.payload)
        fstdin.seek(0)
        print 'CGI: Preparing process object...'
        p=subprocess.Popen([executable]+args+[path],
                           stdin=fstdin,
                           stdout=fstdout,
                           stderr=fstderr,
                           env=env)
        print 'CGI: Sending', len(req.payload), 'bytes of input payload...'
        print time.time(), 'wait() begins.'
        p.wait()
        print time.time(), 'wait() ends.'
        print 'CGI: Pulling stdout/stderr...'
        fstdout.seek(0)
        fstderr.seek(0)
        stdout=fstdout.read()
        if scode:
            stdout=self.DEFAULT_STATUSCODE+stdout
        stderr=fstderr.read()
        print 'CGI: Done sending, now parsing...'
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
        print 'CGI: Buffered stderr:'
        print stderr
        print 'CGI: Pipes closed'
        code=p.returncode
        print 'CGI: Process exit: returned', code, hex(code&0xffffffff)
        return resp
