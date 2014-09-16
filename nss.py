#neXus Service Software

import socket
socket.setdefaulttimeout(0) #non-blocking, ALL OF THEM!!!
import select
import cStringIO
from email.parser import Parser
import urlparse
import urllib
import threading
import thread
from BaseHTTPServer import BaseHTTPRequestHandler #for .responses
import traceback
import time
import sys
import shlex
import cgi
import random
import os
import sys
import cmd
try:
    import msvcrt
except ImportError:
    msvcrt=None
try:
    import winsound
except ImportError:
    winsound=None
try:
    import curses
except ImportError:
    curses=None
#This pretty little hack fixes some typechecking errors
#when running as the main server (which is most of the time)
if __name__=='__main__':
    import nss
else:
    nss=None
VERSION=0x0006A00

VERSION_S='0.6a0'

SERVER='nSS '+VERSION_S

QUOTES=['Don\'t judge my cannon.',
        'And this is my boomstick!',
##        'Your epidermis is showing.',
##        'Serving nope.avi since 1979',
        'Wake up, Mr. Freeman...',
##        'Because you dun goofed.',
##        'Maybe it\'s made of chocolate...',
##        'Can you hear me now?',
        'I take a chip...and eat it!',
        ]

ORIGQUOTES=QUOTES[:]

RUNNING=True

PARSER=Parser()

HTTP_VER=(1, 1)

HTTP_VER_S='HTTP/1.1'

HTTP_ERR_RESPONSE='''<html>
<head>
<title>HTTP %(status)d: %(shortdesc)s</title>
</head>
<body>
<h1>HTTP %(status)d: %(shortdesc)s</h1>
<p>%(longdesc)s</p>
<p><i>neXus Service Software '''+VERSION_S+'''</i></p>
</body>
</html>'''

RESPONSES=BaseHTTPRequestHandler.responses

##class Tee(object):
##    def __init__(self, s1, s2):
##        self.s1=s1
##        self.s2=s2
##    def write(self, data):
##        self.s1.write(data)
##        self.s2.write(data)
##
##sys.stdout=Tee(sys.stdout, open('log.txt', 'a'))        

LOG=open('log.txt', 'a', 0)

PLUGINS={}

print 'nSS Loading plugins:'
sys.path.append('plugins')
for pfile in os.listdir('plugins'):
    if pfile.endswith('.py'):
        print pfile,
        try:
            plmod=__import__(pfile[:-3])
        except Exception, e:
            print 'Failed:', repr(e)
            continue
        print 'Name:', plmod.NAME,
        if hasattr(plmod, 'NOT_PLUGIN'):
            print 'Skipped (NOT_PLUGIN)'
            continue
        PLUGINS[plmod.NAME]=plmod
        print 'Loaded'

PLOBJS={}        

for plmod in PLUGINS.values():
    try:
        PLOBJS[plmod.NAME]=plmod.Plugin()
    except Exception, e:
        print 'Exception occured while trying to load plugin '+plmod.name+' (not loaded!): '+repr(e)
    else:
        print 'Server loaded plugin '+plmod.NAME        

class HTTPError(Exception):
    def __init__(self, status, shortdesc=None, longdesc=None):
        if shortdesc is None:
            shortdesc=RESPONSES[status][0]
        if longdesc is None:
            longdesc=RESPONSES[status][1]
        self.status=status
        self.shortdesc=shortdesc
        self.longdesc=longdesc
        Exception.__init__(self, status, shortdesc, longdesc)
if __name__=='__main__':
    nss.HTTPError=HTTPError

class HTTPDocumentError(HTTPError):
    def __init__(self, doc):
        Exception.__init__(self, doc)
        self.response=doc
if __name__=='__main__':
    nss.HTTPDocumentError=HTTPDocumentError

class HTTPRedirectError(HTTPDocumentError):
    def __init__(self, loc, ver=HTTP_VER_S):
        Exception.__init__(self, loc, ver)
        self.loc=loc
        self.ver=ver
        self.response=HTTPResponse('', 301, ver=ver, compute=False)
        del self.response.headers['Content-type']
        self.response.headers['Location']=loc
        self.response.Compute()
if __name__=='__main__':
    nss.HTTPRedirectError=HTTPRedirectError

class HandleLater(Exception):
    pass

class HTTPSTATE:
    REQUESTING=0
    READING_DATA=1
    RESPONDING=2
    CLOSED=3

class HTTPClient(object):
    RECV_BUFSIZE=4096
    SEND_BUFSIZE=1024
    def __init__(self, sock, peer, handler, env, server):
        self.sock=sock
        self.peer=peer
        self.handler=handler
        self.env=env
        self.server=server
        self.state=HTTPSTATE.REQUESTING
        self.buffer=cStringIO.StringIO()
    def GoRead(self):
        try:
            data=self.sock.recv(self.RECV_BUFSIZE)
        except socket.error:
            self.state=HTTPSTATE.CLOSED
            return
        if not data:
            #Our peer died...oh well...
            self.state=HTTPSTATE.CLOSED
            return
        if self.state==HTTPSTATE.READING_DATA:
            self.dbuffer.write(data)
        else:
            self.buffer.write(data)
    def IsReady(self):
        bufstr=self.buffer.getvalue()
        val=bufstr.replace('\r\n', '\n')
        if self.state==HTTPSTATE.REQUESTING and '\n\n' in val:
            #Check for a Content-length header. It's existence is (our)
            #sure sign that some data follows.
            http, sep, payload=bufstr.partition('\n')
            em=PARSER.parsestr(payload, True)
            if 'Content-length' in em:
                try:
                    self.contentlen=int(em['Content-length'])
                except ValueError:
                    return True #Go ahead with this request as if it had no data...
                #Restore the buffer to only containing data up to the \n\n
                #Note that only \r\n\r\n and \n\n are legal terminators. (Not \r\r.)
                idx=bufstr.index('\r\n\r\n')
                if not idx<0:
                    self.buffer.seek(idx+4)
                    self.buffer.truncate()
                else:
                    idx=bufstr.index('\n\n')
                    if not idx<0:
                        self.buffer.seek(idx+2)
                        self.buffer.truncate()
                #Tell everyone we're expecting data
                self.state=HTTPSTATE.READING_DATA
                self.env.ClientReadingData(self)
                self.dbuffer=cStringIO.StringIO() #The new data buffer
                self.dbuffer.write(em.get_payload())
                if self.dbuffer.tell()>=self.contentlen:
                    #Oops, the buffer is filled already. Yeah, we're ready.
                    self.dbuffer.seek(self.contentlen)
                    self.dbuffer.truncate()
                    return True
            else:
                return True #No data :D
        if self.state==HTTPSTATE.READING_DATA:
            if self.dbuffer.tell()>=self.contentlen:
                self.dbuffer.seek(self.contentlen)
                self.dbuffer.truncate()
                return True
    def Handle(self):
        try:
            if self.state==HTTPSTATE.READING_DATA:
                self.buffer=self.handler.Handle(self, cStringIO.StringIO(self.buffer.getvalue()+self.dbuffer.getvalue()))
            else:
                self.buffer=self.handler.Handle(self, cStringIO.StringIO(self.buffer.getvalue()))
            if not isinstance(self.buffer, (HTTPResponse, nss.HTTPResponse)):
                self.buffer=HTTPResponse(self.buffer)
            #Allow the plugins to play with the response buffer
            for plg in PLOBJS.values():
                self.buffer=plg.FilterResponse(self, self.buffer, self.lastreq)
        except (HTTPError, nss.HTTPError), e:
            if hasattr(e, 'response'):
                self.buffer=e.response
                if not isinstance(self.buffer, (HTTPResponse, nss.HTTPResponse)):
                    self.buffer=HTTPResponse(self.buffer)
                self.env.ClientErrorDocument(self, e)
            else:
                self.buffer=HTTPResponse(HTTP_ERR_RESPONSE%{'status': e.status,
                                                            'shortdesc': e.shortdesc,
                                                            'longdesc': e.longdesc},
                                         e.status,
                                         ver=self.lastreq.ver_s)
                self.env.ClientErrorHTTP(self, e)
            self.state=HTTPSTATE.RESPONDING
            return None
        except Exception, e:
            s=traceback.format_exc()
            self.env.ClientError(self, e, s)
            self.buffer=HTTPResponse(HTTP_ERR_RESPONSE%{'status': 500,
                                                        'shortdesc': 'Server Error',
                                                        'longdesc': 'Exception happened during handling of request.'},
                                     500,
                                     ver=self.lastreq.ver_s)
            self.state=HTTPSTATE.RESPONDING
            return e, s
        else:
            return None
    def Revert(self): #For persistent connections, reset conn state
        self.state=HTTPSTATE.REQUESTING
        self.buffer=cStringIO.StringIO()
    def GoWrite(self):
        pos=self.buffer.tell()
        data=self.buffer.read(self.SEND_BUFSIZE)
        try:
            sent=self.sock.send(data)
        except socket.error, e:
            #Tried to write to a dead socket
            self.state=HTTPSTATE.CLOSED
            return
        self.buffer.seek(pos+sent)
        #While this eof test looks awkward, it spares us from having
        #to create a str object just to take its len.
        test=self.buffer.read(1)
        if not test:
            self.env.ClientReqDone(self, self.buffer.tell())
            if self.lastreq and self.lastreq.headers and 'Connection' in self.lastreq.headers and self.lastreq.headers['Connection'].lower()=='keep-alive':
                self.env.ClientReverting(self)
                self.Revert()
            else:
                self.state=HTTPSTATE.CLOSED
        else:
            self.buffer.seek(self.buffer.tell()-1)
    def fileno(self):
        return self.sock.fileno()
if __name__=='__main__':
    nss.HTTPClient=HTTPClient

class HTTPRequest(object):
    def __init__(self, reqf, parse=True):
        self.reqf=reqf
        self.method=None
        self.urn=None
        self.version=None
        self.ver_s=None
        self.headers=None
        self.payload=None
        self.invalid=False
        if parse:
            self.Parse()
    def Parse(self):
        #Lop off the first line and parse it as the HTTP command
        line=self.reqf.readline()
        parts=line.strip().split()
        if len(parts)!=3: #Bad, bad, bad...
            self.invalid=True
            return
        self.method, self.urn, self.version=parts
        #Unquote the URN to its canonical form
        self.urn_s=self.urn
        self.urn=urlparse.urlparse(self.urn)
        self.path=urllib.unquote(self.urn.path)
        self.query=urllib.unquote_plus(self.urn.query)
        #Make sure the version is right
        self.ver_s=self.version
        if not self.version.startswith('HTTP/'):
            self.invalid=True
            return
        try:
            self.version=map(int, self.version[5:].split('.'))
        except ValueError:
            self.invalid=True
            return
        if len(self.version)!=2:
            self.invalid=True
            return
        em=PARSER.parse(self.reqf, True) #Headers only,
        #(which if you read into email.feedparser.FeedParser's
        #docstring, says that all the rest of the data gets
        #crammed into the payload).
        self.headers=em #Thanks, dict-like access!
        self.payload=em.get_payload()
        #Perhaps we have arguments?
        #Woo! Some fun...the cgi module is good at parsing this
        #kind of data, but it reads a lot of it from the environment,
        #so we must fake an environment to allow it to set up some
        #important variables.
        #Unfortunately, FieldStorage bases a LOT of its important
        #functionality, like parsing qs_on_post, on the fact that
        #it's headers are missing (id est headers is None). Therefore,
        #even though the data is within reach, I'm telling FieldStorage
        #to look for it just for the fact that it will do a little
        #extra (important) work.
        #XXX qs_on_post or content-disposition? You decide :/ ...
        env={'REQUEST_METHOD': self.method,
             'QUERY_STRING': self.urn.query}
        if 'Content-type' in self.headers:
            env['CONTENT_TYPE']=self.headers['Content-type']
        if 'Content-length' in self.headers:
            env['CONTENT_LENGTH']=self.headers['Content-length']
        if self.method=='GET':
            #Tell FieldStorage to actually parse the query string
            #as if it were...a query string, not text/plain
            env['CONTENT_TYPE']='application/x-www-form-urlencoded'
        self.formdata=cgi.FieldStorage(cStringIO.StringIO(self.payload),
##                                       self.headers, #Comment this line if you prefer qs_on_post
                                       environ=env)
        #If, for some reason, this isn't a list of form data, say so.
        if not self.formdata.list:
            self.formdata=self.formdata.value
if __name__=='__main__':
    nss.HTTPRequest=HTTPRequest

class HTTPResponse(object):
    def __init__(self, payload, status=200, contenttype='text/html', headers=None, ver=HTTP_VER_S, compute=True):
        self.status=status
        self.desc=RESPONSES[status][0]
        self.ver=ver
        self.payload=payload
        if isinstance(self.payload, str):
            self.payload=cStringIO.StringIO(self.payload)
        if isinstance(self.payload, file):
            self.payload=cStringIO.StringIO(self.payload.read())
        if isinstance(self.payload, cStringIO.OutputType):
            self.payload=cStringIO.StringIO(self.payload.getvalue()) #Convert to StringI
        self.headers={'Content-type': contenttype, 'Content-length': len(self.payload.getvalue())}
        self.headers['Server']=SERVER+' ('+random.choice(QUOTES)+')'
        if headers:
            self.headers.update(headers)
        self.fp=None
        if compute:
            self.Compute()
    def Compute(self):
        self.fp=cStringIO.StringIO()
        self.fp.write('%s %d %s\r\n'%(self.ver, self.status, self.desc))
        for key, value in self.headers.iteritems():
            self.fp.write('%s: %s\r\n'%(key, value))
        self.fp.write('\r\n'+self.payload.getvalue())
        #Convert to the other StringIO type
        self.fp=cStringIO.StringIO(self.fp.getvalue())
    def __getattr__(self, attr):
        return getattr(self.fp, attr)
if __name__=='__main__':
    nss.HTTPResponse=HTTPResponse

class HTTPRawResponse(HTTPResponse):
    def __init__(self, payload):
        self.payload=payload
        if isinstance(self.payload, str):
            self.payload=cStringIO.StringIO(self.payload)
        if isinstance(self.payload, file):
            self.payload=cStringIO.StringIO(self.payload.read())
        if isinstance(self.payload, cStringIO.OutputType):
            self.payload=cStringIO.StringIO(self.payload.getvalue()) #Convert to StringI
    def __getattr__(self, attr):
        return getattr(self.payload, attr)
if __name__=='__main__':
    nss.HTTPRawResponse=HTTPRawResponse

class Path(object):
    def __init__(self, s, local='/'):
        if not s.startswith('/'):
            s=local+s
        self.path=s
    @classmethod
    def Make(cls, o):
        if isinstance(o, Path):
            return o
        return cls(o)
    @property
    def Dir(self):
        return self.path.endswith('/')
    @property
    def Components(self):
        return filter(None, self.path.split('/'))
    def __len__(self):
        return len(self.Components)
    def __gt__(self, other):
        return len(self)>len(other)
    def __lt__(self, other):
        return len(self)<len(other)
    def __eq__(self, other):
        return self.path==other.path
    def __ne__(self, other):
        return not self==other
    def __str__(self):
        return self.path
    def IsSubDir(self, parent):
        ppath=Path.Make(parent)
        if self<parent:
            return False
        for scmp, pcmp in zip(self.Components, ppath.Components):
            if scmp!=pcmp:
                return False
        return True
    def Local(self, subpath):
        sp=Path.Make(subpath)
        i=0
        for scmp, ocmp in zip(self.Components, sp.Components):
            if scmp!=ocmp:
                break
            i+=1
        return Path.Make('/'.join(sp.Components[i:]))

class VServer(object):
    def __init__(self, hname):
        self.hname=hname
        self.mounts={}
    def AddMount(self, path, manager):
        self.mounts[str(path)]=manager
    def RemoveMount(self, path):
        try:
            del self.mounts[str(path)]
        except KeyError:
            pass
    def IterPaths(self):
        for path in sorted(self.mounts.keys(), reverse=True):
            yield Path.Make(path)
    def RemoveRecurse(self, path):
        newmounts={}
        path=Path.Make(path)
        for pth in self.IterPaths():
            if not pth.IsSubDir(path):
                newmounts[str(pth)]=self.mounts[str(pth)]
        self.mounts=newmounts
    def CanHandle(self, req):
        return 'Host' in req.headers and req.headers['Host']==self.hname
    def Handle(self, client, req, server):
        req.path=Path.Make(req.path)
        for pth in self.IterPaths():
            if req.path.IsSubDir(pth):
                req.localpath=pth.Local(req.path)
                print 'VServ will handle request for', str(req.path), 'using mount at', str(pth), 'and local', str(req.localpath)
                man=self.mounts[str(pth)]
                if not getattr(man, 'enabled', True):
                    continue #Manager is disabled...
                #Allow plugins to override the normal action of a *SINGLE MANAGER*
                for plg in PLOBJS.values():
                    doc=plg.Handle(man, client, req, server)
                    if doc:
                        break
                else:
                    doc=man.Handle(client, req, server)
                return doc
        print 'VServ did not find a good mount'
        return None #We could not find a handler, perhaps another VServer can...

PRIMARY_VSERVERS=[]
if nss:
    nss.PRIMARY_VSERVERS=PRIMARY_VSERVERS #So other modules can link to it

#You can subclass this. But subclassing HTTPManager is more accepted. Your choice.
class HTTPHandler(object):
##    MANAGERS=[]
    MODIFIERS=[]
    def __init__(self, server):
        self.server=server
        self.vservers=PRIMARY_VSERVERS
##    @classmethod
##    def AddManager(cls, manager):
##        cls.MANAGERS.append(manager)
##    @classmethod
##    def InsertManager(cls, idx, manager): 
##        cls.MANAGERS.insert(max((min((idx, len(cls.MANAGERS))), 0)), manager)
##    @classmethod
##    def RemoveManager(cls, manager):
##        try:
##            cls.MANAGERS.remove(manager)
##        except ValueError:
##            pass
    def AddVServer(self, vserv):
        self.vservers.append(vserv)
    def RemoveVServer(self, vserv):
        try:
            self.vservers.remove(vserv)
        except ValueError:
            pass
    @classmethod
    def GetManagers(cls):
        return cls.MANAGERS
    @classmethod
    def AddModifier(cls, mod):
        cls.MODIFIERS.append(mod)
    @classmethod
    def InsertModifier(cls, idx, mod):
        cls.MODIFIERS.insert(max((min((idx, len(cls.MODIFIERS))), 0)), mod)
    @classmethod
    def RemoveModifier(cls, mod):
        try:
            cls.MODIFIERS.remove(mod)
        except ValueError:
            pass
    @classmethod
    def GetModifiers(cls):
        return cls.MODIFIERS
    def Handle(self, client, reqf):
        try:
            req=HTTPRequest(reqf)
        except Exception, e:
            raise HTTPError(400, longdesc='Malformed request syntax')
        client.lastreq=req
        lastman=None
        if req.invalid:
            raise HTTPError(400)
        try:
##            for man in self.MANAGERS:
##                lastman=man
##                if not getattr(man, 'enabled', True):
##                    continue
##                #Allow plugins to override the normal action of a *SINGLE MANAGER*
##                for plg in PLOBJS.values():
##                    doc=plg.Handle(man, client, req, server)
##                    if doc:
##                        break
##                else:
##                    doc=man.Handle(client, req, server)
##                if doc is not None:
##                    for mod in self.MODIFIERS:
##                        resp=mod.Handle(client, req, doc, man, False, server)
##                        if resp:
##                            doc=resp
##                            man=mod
##                    return doc
            print 'Recevied request for host', (req.headers['Host'] if 'Host' in req.headers else 'No host!')
            for vserv in self.vservers:
                if vserv.CanHandle(req):
                    print 'VirtualServer at', vserv.hname, 'will handle this'
                    doc=vserv.Handle(client, req, self.server)
                    if doc:
                        return doc
            else:
                #Look for a "main domain" vserv
                for vserv in self.vservers:
                    if vserv.hname=='.':
                        print 'VirtualServers with . hname will handle this'
                        doc=vserv.Handle(client, req, self.server)
                        if doc:
                            return doc
                else:
                    raise HTTPError(404, longdesc='An appropriate handler was not found to service your request.')
        except Exception, e:
##            for mod in self.MODIFIERS:
##                resp=mod.HandleError(client, req, e, lastman, server)
##                if resp is None:
##                    continue
##                if resp is False:
##                    raise
##                doc=resp
##                for mod in self.MODIFIERS:
##                    resp=mod.Handle(client, req, doc, lastman, True, server)
##                    if resp:
##                        doc=resp
##                        lastman=mod
##                return doc
            raise
if __name__=='__main__':
    nss.HTTPHandler=HTTPHandler

class HTTPManager(object):
    def Handle(self, client, req):
        raise NotImplementedError('HTTPManager subclass must implement .Handle()')
if __name__=='__main__':
    nss.HTTPManager=HTTPManager

class HTTPModifier(object):
    def Handle(self, client, req, resp, creator, fromerror, server):
        pass
    def HandleError(self, client, req, err, cause, server):
        pass
if __name__=='__main__':
    nss.HTTPModifier=HTTPModifier

class HTTPClientManager(threading.Thread):
    TMOUT=0.1 #See .run()
    def __init__(self, server, hclass=HTTPHandler):
        threading.Thread.__init__(self)
        self.server=server
        self.clients=[] #Why a list and not a set?
        self.clilock=threading.Lock()
        self.hclass=hclass
        #Because it means we don't have to instantiate
        #a list each time we get to select.
    def AddClient(self, sock, addr):
        cl=HTTPClient(sock, addr, self.hclass(self.server), self.server.env, self.server)
        self.server.env.ClientNew(cl)
        with self.clilock:
            self.clients.append(cl)
    def PruneClients(self):
        torem=set()
        with self.clilock:
            for client in self.clients:
                if client.state==HTTPSTATE.CLOSED:
                    torem.add(client)
            for client in torem:
                self.clients.remove(client)
                self.server.env.ClientDead(client)
    def run(self):
        while RUNNING: #Lather, rinse, repeat...
            try:
                with self.clilock:
                    clis=self.clients[:]
                if not clis:
                    #No one's here yet...
                    time.sleep(self.TMOUT)
                    continue
                #In order to conserve resources, we're going to seperate the clients
                #into two lists: the ones that need to continue reading (i.e. state
                #HTTPSTATE.REQUESTING) and ones that need to write (state HTTPSTATE.
                #RESPONDING). The latter is important; most healthy sockets, even
                #nonblocking, have enough buffer space for writing, and finding this
                #out for no reason will chew CPU.
                rd, wr, ex=select.select([i for i in clis if i.state==HTTPSTATE.REQUESTING or i.state==HTTPSTATE.READING_DATA],
                                         [i for i in clis if i.state==HTTPSTATE.RESPONDING],
                                          [], self.TMOUT) #The small timeout here
                #ensures that we'll pick up changes in the clients list in at most
                #timeout seconds. It has to be optimal for connecting clients, but
                #at the same time balanced for server resources.
                for cli in rd:
                    if cli.state==HTTPSTATE.REQUESTING or cli.state==HTTPSTATE.READING_DATA:
                        cli.GoRead()
                        if cli.IsReady():
                            try:
                                cli.Handle()
                            except HandleLater:
                                pass
                            else:
                                cli.state=HTTPSTATE.RESPONDING
                                self.server.env.ClientResponding(cli)
                for cli in wr:
                    if cli.state==HTTPSTATE.RESPONDING:
                        cli.GoWrite() #State transitions happen in there.
                if rd or wr:
                    self.PruneClients()
            except ValueError, e:
                if 'select()' in e:
                    self.server.env.WriteError('We recieved notification of a failed select, possibly due to too many requesters! I\'m going to panic and drop all the clients immediately...')
                with self.clilock:
                    self.clients=[]
                self.server.env.WriteError('ValueError '+repr(e)+' occured in ClientManager thread')
                traceback.print_exc()
            except TypeError, e:
                self.server.env.WriteError('TypeError '+repr(e)+' occured in ClientManager thread')
                traceback.print_exc()
                if winsound:
                    winsound.Beep(4000, 50)
                    winsound.Beep(4400, 100)
            except Exception, e:
                self.server.env.WriteError('Exception '+repr(e)+' occured in ClientManager thread')
                traceback.print_exc()
        print 'Client manager thread: exiting, goodbye...'
if __name__=='__main__':
    nss.HTTPClientManager=HTTPClientManager

class HTTPServer(threading.Thread):
    TMOUT=5 #See .run()
    def __init__(self, env, addr, listen=5, start=True):
        threading.Thread.__init__(self)
        self.env=env
        env.server=self
        self.sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(addr)
        self.addr=addr
        self.sock.listen(listen)
        self.climan=HTTPClientManager(self)
        for plg in PLOBJS.values():
            try:
                plg.Load(self)
            except Exception, e:
                self.env.WriteError('Exception occured during plugin init: '+repr(plg)+' '+repr(e))
                traceback.print_exc()
            else:
                self.env.WriteInfo('Initted plugin '+repr(plg))
        if start:
            self.Start()
    def Start(self):
        self.env.Start()
        self.start()
        self.climan.start()
    def run(self):
        while RUNNING:
            try:
                rd, wr, ex=select.select([self.sock], [], [], self.TMOUT)
                if rd:
                    sock, addr=self.sock.accept()
                    self.climan.AddClient(sock, addr)
            except Exception, e:
                self.env.WriteError('Exception '+repr(e)+' happened in server .accept() thread')
                traceback.print_exc()
        print 'Server intake thread: exiting, goodbye...'
if __name__=='__main__':
    nss.HTTPServer=HTTPServer

class BaseHTTPEnvironment(object):
    def __init__(self):
        self.server=None #but it will get set
    def Start(self):
        self.WriteNotice('%s nSS Server starting, address %r...'%(VERSION_S, self.server.addr,))
    def ClientNew(self, client):
        self.WriteInfo(str(client.peer)+': New connection')
    def ClientResponding(self, client):
        self.WriteNotice(str(client.peer)+': Finished request for '+client.lastreq.urn_s)
    def ClientErrorDocument(self, client, e):
        self.WriteWarning(str(client.peer)+': Responded with error document')
    def ClientErrorHTTP(self, client, e):
        self.WriteWarning(str(client.peer)+': Responded with error code '+str(e.status))
    def ClientError(self, client, e, tb):
        self.WriteError(str(client.peer)+': Experienced error during handling of request:\n'+tb)
    def ClientReqDone(self, client, bytes):
        self.WriteInfo(str(client.peer)+': Finished response; '+str(bytes)+' bytes sent.')
    def ClientReverting(self, client):
        self.WriteInfo(str(client.peer)+': Client reverting on a keep-alive')
    def ClientReadingData(self, client):
        self.WriteInfo(str(client.peer)+': Client began sending data')
    def ClientDead(self, client):
        self.WriteInfo(str(client.peer)+': Connection lost')
    def WriteInfo(self, s):
        self.Write(s, 'INFO')
    def WriteNotice(self, s):
        self.Write(s, 'NOTICE')
    def WriteWarning(self, s):
        self.Write(s, 'WARNING')
    def WriteError(self, s):
        self.Write(s, 'ERROR')
    def Format(self, s, level):
        return '[%(level)-8s] %(time)s %(msg)s'%{'level': level, 'time': time.ctime(), 'msg': s}
    def Write(self, s, level):
        raise NotImplementedError('BaseHTTPEnvironment derivative must, at least, implement .Write()')

class ConsoleHTTPEnvironment(BaseHTTPEnvironment, cmd.Cmd):
    def Write(self, s, level):
        sys.stdout.write(self.Format(s, level)+'\n')
        LOG.write(self.Format(s, level)+'\n')
    def do_mount(self, line):
        '''
mount <host> <path> <module> <class>

Loads a module, then puts the HTTPManager into that VServer whose
hostname is host at the specified mount path. If the VServer doesn't
exist, it is created. If the mount overrides what would normally be
served from another manager, that part of the mount is essentially
nullified. A parameter, as a string, can optionally be passed to the
constructor of the HTTPManager, and is passed directly in unchanged
(if it involves spaces, wrap the entire class spec in quotes as per
shlex). Historically, this parameter has been known to accept mount
path names, but this should no longer be the case.'''
        parts=shlex.split(line)
        host=parts[0]
        mount=parts[1]
        modname=parts[2]
        cspec=parts[3]
        g=globals()
        if modname in g:
            mod=g[modname]
            mod=reload(mod)
            self.WriteInfo('Reloaded module '+modname)
        else:
            try:
                mod=__import__(modname)
            except ImportError:
                self.WriteError('Cannot import module '+modname)
                return
            self.WriteInfo('Located and loaded module '+modname)
        g[modname]=mod
        cname, sep, param=cspec.partition(';')
        cls=getattr(mod, cname, None)
        if cls is None:
            self.WriteError('Failed to load class '+cname)
        else:
            if param:
                inst=cls(param)
            else:
                inst=cls()
            for vserv in PRIMARY_VSERVERS:
                if vserv.hname==host:
                    vserv.AddMount(mount, inst)
                    break
            else:
                PRIMARY_VSERVERS.append(VServer(host))
                PRIMARY_VSERVERS[-1].AddMount(mount, inst)
            self.WriteInfo('Added '+cname+' to managers list')
    def do_unmount(self, line):
        '''
unmount <host> <path>

Unmounts the HTTPManager at the given host or mount
(assuming it exists).'''
        parts=shlex.split(line)
        host=parts[0]
        path=parts[1]
        for vserv in PRIMARY_VSERVERS:
            if vserv.hname==host:
                vserv.RemoveMount(path)
                self.WriteInfo('Unmounted.')
        else:
            self.WriteError('Could not find virtual server with that host name')
    def do_unmountall(self, line):
        '''
unloadall

Unloads all HTTPManagers.'''
        global PRIMARY_VSERVERS
        PRIMARY_VSERVERS=[]
        if nss:
            nss.PRIMARY_VSERVERS=PRIMARY_VSERVERS
        self.WriteInfo('Done')
    def do_modload(self, line):
        '''
modload <module> <class> [<class> [...]]
<class>=<classname>[;<param>]

Loads a module, and puts HTTPModifier derivatives into the default HTTPHandler.
If the module is present in globals(), it is reloaded instead.
A parameter can be optionally split from the classname after a semicolon. The
exact text of this parameter is passed into the class' constructor.'''
        parts=shlex.split(line)
        modname=parts[0]
        classes=parts[1:]
        g=globals()
        if modname in g:
            mod=g[modname]
            mod=reload(mod)
            self.WriteInfo('Reloaded module '+modname)
        else:
            try:
                mod=__import__(modname)
            except ImportError:
                self.WriteError('Cannot import module '+modname)
                return
            self.WriteInfo('Located and loaded module '+modname)
        g[modname]=mod
        for cdef in classes:
            cname, sep, param=cdef.partition(';')
            cls=getattr(mod, cname, None)
            if cls is None:
                self.WriteError('Failed to load class '+cname)
            else:
                if param:
                    HTTPHandler.AddModifier(cls(param))
                else:
                    HTTPHandler.AddModifier(cls())
                self.WriteInfo('Added '+cname+' to managers list')
    def do_modloadpre(self, line):
        '''
modloadpre <module> <class> [<class> [...]]
<class>=<classname>[;<param>]

As modload, but will prepend the instantiated modifiers.
Note that, if you specify more than one class, they will be loaded in reverse order!
'''
        parts=shlex.split(line)
        modname=parts[0]
        classes=parts[1:]
        g=globals()
        if modname in g:
            mod=g[modname]
            mod=reload(mod)
            self.WriteInfo('Reloaded module '+modname)
        else:
            try:
                mod=__import__(modname)
            except ImportError:
                self.WriteError('Cannot import module '+modname)
                return
            self.WriteInfo('Located and loaded module '+modname)
        g[modname]=mod
        for cdef in classes:
            cname, sep, param=cdef.partition(';')
            cls=getattr(mod, cname, None)
            if cls is None:
                self.WriteError('Failed to load class '+cname)
            else:
                if param:
                    HTTPHandler.InsertModifier(0, cls(param))
                else:
                    HTTPHandler.InsertModifier(0, cls())
                self.WriteInfo('Added '+cname+' to managers list')
    def do_modloadins(self, line):
        '''
modloadins <idx> <module> <class> [<class> [...]]
<class>=<classname>[;<param>]

As modload, but inserts into the specified index.
As modloadpre, it will also load in reverse order of specification.
'''
        parts=shlex.split(line)
        idx=int(parts[0])
        modname=parts[1]
        classes=parts[2:]
        g=globals()
        if modname in g:
            mod=g[modname]
            mod=reload(mod)
            self.WriteInfo('Reloaded module '+modname)
        else:
            try:
                mod=__import__(modname)
            except ImportError:
                self.WriteError('Cannot import module '+modname)
                return
            self.WriteInfo('Located and loaded module '+modname)
        g[modname]=mod
        for cdef in classes:
            cname, sep, param=cdef.partition(';')
            cls=getattr(mod, cname, None)
            if cls is None:
                self.WriteError('Failed to load class '+cname)
            else:
                if param:
                    HTTPHandler.InsertModifier(idx, cls(param))
                else:
                    HTTPHandler.InsertModifier(idx, cls())
                self.WriteInfo('Added '+cname+' to managers list')
    def do_modunload(self, line):
        '''
modunload <modname>

Unloads all HTTPModifiers whose module is modname.'''
        for man in HTTPHandler.MODIFIERS[:]:
            if man.__class__.__module__==line:
                self.WriteInfo('Deleted '+str(type(man))+' from modifiers')
                HTTPHandler.RemoveModifier(man)
    def do_modunloadclass(self, line):
        '''
modunload <clsname>

Unloads all HTTPModifiers with the given class name.'''
        for man in HTTPHandler.MODIFIERS[:]:
            if man.__class__.__name__==line:
                self.WriteInfo('Deleted '+str(type(man))+' from modifiers')
                HTTPHandler.RemoveModifier(man)
    def do_modunloadall(self, line):
        '''
unloadall

Unloads all HTTPModifiers derivatives.'''
        HTTPHandler.MODIFIERS=[]
        self.WriteInfo('Done')
    def do_show(self, line):
        '''
show

Shows the list of loaded HTTPManager derivatives.'''
        for vserv in PRIMARY_VSERVERS:
            print '@', vserv.hname, ':'
            for pth in vserv.IterPaths():
                man=vserv.mounts[str(pth)]
                print '\t', str(pth), '\t', repr(man), ('(Enabled)' if getattr(man, 'enabled', True) else '(Disabled)')
    def do_exec(self, line):
        '''
exec <file>

Executes all the commands in a file as if they were typed in the console.'''
        for fline in open(line, 'rb'):
            self.onecmd(fline.strip())
    def do_sendcmd(self, line):
        '''
sendcmd <host> <path> <cname> <param>

Sends a command to an HTTPManager by host and mount path.
'''
        parts=shlex.split(line)
        host=parts[0]
        path=parts[1]
        cname=parts[2]
        args=' '.join(parts[3:])
        for vserv in PRIMARY_VSERVERS:
            if vserv.hname==host:
                man=vserv.mounts[path]
        else:
            self.WriteError('Cannot find virtual server by hostname')
            return
        if not hasattr(man, 'do_'+cname):
            self.WriteError('Command not found')
            return
        getattr(man, 'do_'+cname)(args)
        self.WriteInfo('Done')
    def do_pllist(self, line):
        '''pllist

Lists all loaded plugins.'''
        for pname in PLUGINS.keys():
            self.Write(pname)
    def do_pldesc(self, line):
        '''pldesc <plugin>

Give a brief description of the named plugin.'''
        if line in PLUGINS:
            self.Write(PLUGINS[line].DESC)
        else:
            self.WriteError('Plugin not found.')
    def do_plunload(self, line):
        '''plunload <plugin>

Unlods the specified plugin.
NOTE: The current architecture prevents the plugin from being reloaded. You must restart the server if you want to reload the plugin. Sorry.'''
        if line in PLOBJS:
            PLOBJS[line].Unload()
        else:
            self.WriteError('Plugin not found.')
    def do_plcmd(self, line):
        '''plcmd <plugin> <command> <params...>

Sends a command to a plugin by name.'''
        parts=line.split(' ')
        plname, cmd=parts[0], parts[1]
        line=parts[2:]
        if plname in PLOBJS:
            if hasattr(PLOBJS[plname], 'do_'+cmd):
                getattr(PLOBJS[plname], 'do_'+cmd)(line)
            else:
                self.WriteError('Command not found.')
        else:
            self.WriteError('Plugin not found.')
        self.WriteInfo('Done.')
    def do_listcmds(self, line):
        '''listcmds <idx>

Lists all the commands that can be sent to the manager at the given index.'''
        man=HTTPHandler.MANAGERS[int(line)]
        print [i[3:] for i in dir(man) if i.startswith('do_')]
    def do_helpcmd(self, line):
        '''helpcmd <host> <path> <cname>

Prints out the documentation on the given command of the manager by host and mount path.'''
        parts=shlex.split(line)
        host=parts[0]
        path=parts[1]
        cname=parts[2]
        for vserv in PRIMARY_VSERVERS:
            if vserv.hname==host:
                man=vserv.mounts[path]
        else:
            self.WriteError('Cannot find virtual server by hostname')
            return
        if not hasattr(man, 'do_'+cname):
            self.WriteError('Command not found')
            return
        print getattr(man, 'do_'+cname).__doc__ or 'No documentation.'
    def do_enable(self, line):
        '''enable <host> <path> [<enable>]

Enables or disables a manager by host and mount path. Second argument must be 0 to disable.'''
        parts=shlex.split(line)
        host=parts[0]
        path=parts[1]
        for vserv in PRIMARY_VSERVERS:
            if vserv.hname==host:
                man=vserv.mounts[path]
        else:
            self.WriteError('Cannot find virtual server by hostname')
            return
        if len(parts)==1:
            enable=True
        else:
            enable=parts[1].strip()!='0'
        self.WriteInfo(repr(man)+' '+('Enabled' if enable else 'Disabled'))
        man.enabled=enable
    def do_setquote(self, line):
        '''setquote <quote>

Clears all quotes, then sets them to contain only the single quote specified.'''
        global QUOTES
        QUOTES=[line]
    def do_addquote(self, line):
        '''adquote <quote>

Adds a quotes to the list of available quotes.'''
        QUOTES.append(line)
    def do_showquotes(self, line):
        '''showquotes

Shows all quotes that can be used on a Server: header.'''
        print QUOTES
    def do_resetquotes(self, line):
        '''resetquotes

Resets the quotes to the default ones provided.'''
        global QUOTES
        QUOTES=ORIGQUOTES[:]
    def do_shell(self, line):
        '''shell <cmd>
!<cmd>

Executes Python code in the context of the global namespace.
For convenience, the following are available:
-env refers to the Environment derivative currently running,
-server refers to env.server, the HTTPServer,
-hh is the class HTTPHandler.'''
        exec line in globals(), {'env': self, 'server': self.server, 'hh': HTTPHandler}
    def do_stop(self, line):
        '''stop

Shuts down the server gently...ish.'''
        global RUNNING
        RUNNING=False
        #In order to finalize this, we need to wake up all
        #threads. Main is awake on a one-second loop, the
        #server does acquiry every 5 seconds, and the client
        #manager every fraction of a second. Our UIthread will
        #respond to a character, so lets put one on there:
        if curses:
            curses.ungetch('\x00')
        elif msvcrt:
            msvcrt.putch('\x00')
        #else, panic.
        #after that's done, all the threads should realize that
        #it's time to pack up.
        print 'This will take up to 5 seconds...'

if curses:
    class UIThread(threading.Thread):
        def __init__(self, env):
            threading.Thread.__init__(self)
            self.env=env
            self.scr=env.scr
            self.kbbuf=env.kbbuf
        def run(self):
            while RUNNING:
                ch=self.scr.getch()
                if 0<=ch<256:
                    ch=chr(ch)
                else:
                    continue
                if ch=='\b' and self.kbbuf.getvalue():
                    self.kbbuf.seek(self.kbbuf.tell()-1)
                    self.kbbuf.truncate()
                elif ch=='\n' or ch=='\r':
                    self.env.AcceptCommand(self.kbbuf.getvalue())
                    self.kbbuf.seek(0)
                    self.kbbuf.truncate()
                elif ch=='\x00' or ch=='\xe0':
                    pass
                else:
                    self.kbbuf.write(ch)
                self.env.DisplayBuffer()
            print 'UI thread: exiting, goodbye...'
    class CursesConsoleHTTPEnvironment(ConsoleHTTPEnvironment):
        def __init__(self):
            ConsoleHTTPEnvironment.__init__(self)
            self.scr=curses.initscr()
            print '--Got a screen'
            curses.noecho()
            print '--Noecho engaged'
            curses.cbreak()
            print '--Cbreak engaged'
            self.scr.keypad(1)
            print '--Keypad enabled'
            curses.start_color()
            print '--Color engaged'
            maxy, maxx=self.scr.getmaxyx()
            print '--Got dimensions'
            self.term=self.scr.subwin(maxy-1, maxx, 0, 0)
            print '--Created terminal subwindow'
            self.command=self.scr.subwin(1, maxx, maxy, 0)
            print '--Created command subwindow'
            self.command.bkgdset(ord(' '), curses.color_pair(curses.COLOR_BLUE))
            print '--Set background color'
            self.kbbuf=cStringIO.StringIO()
##            self.uit=UIThread(self)
##            self.uit.start()
        def __del__(self):
            self.scr.keypad(0)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
        def Write(self, s, level):
            if level=='ERROR':
                at=curses.color_pair(curses.COLOR_RED)
            elif level=='WARNING':
                at=curses.color_pair(curses.COLOR_YELLOW)
            elif level=='NOTICE':
                at=curses.color_pair(curses.COLOR_CYAN)
            else:
                at=0
            self.term.addstr(self.Format(s, level)+'\n', at)
            LOG.write(self.Format(s, level)+'\n')
            self.term.refresh()
        def DisplayBuffer(self):
            self.command.addstr(0, 0, self.kbbuf.getvalue())
            self.command.refresh()
        def AcceptCommand(self, cmd):
            self.term.addstr('>>> '+cmd+'\n', curses.color_pair(curses.COLOR_BLUE))
            LOG.write('>>> '+cmd+'\n')
            try:
                self.onecmd(cmd)
            except Exception, e:
                s=traceback.format_exc()
                self.term.addstr('Exception occured during processing of command:\n'+s, curses.color_pair(curses.COLOR_RED))
            self.term.refresh()
        def precmd(self, line):
            return line.partition('#')[0] #Derp derp derp derp...see below
elif msvcrt:
    class UIThread(threading.Thread):
        def __init__(self, env):
            threading.Thread.__init__(self)
            self.env=env
            self.kbbuf=env.kbbuf #We'll share this object
        def run(self):
            while RUNNING:
                ch=msvcrt.getch()
                if ch=='\b' and self.kbbuf.getvalue():
                    self.kbbuf.seek(self.kbbuf.tell()-1)
                    self.kbbuf.truncate()
                elif ch=='\n' or ch=='\r':
                    self.env.AcceptCommand(self.kbbuf.getvalue())
                    self.kbbuf.seek(0)
                    self.kbbuf.truncate()
                elif ch=='\x00' or ch=='\xe0':
                    pass
                else:
                    self.kbbuf.write(ch)
                self.env.DisplayBuffer()
            print 'UI thread: exiting, goodbye...'
                
    class MSConsoleHTTPEnvironment(ConsoleHTTPEnvironment):
        def __init__(self):
            ConsoleHTTPEnvironment.__init__(self)
            self.stdout=sys.stdout
            self.kbbuf=cStringIO.StringIO()
            self.uit=UIThread(self)
            self.uit.start()
        def Write(self, s, level):
            self.stdout.write('\r'+' '*79+'\r')
            self.stdout.write(self.Format(s, level)+'\n'+self.kbbuf.getvalue())
            LOG.write(self.Format(s, level)+'\n')
        def DisplayBuffer(self):
            self.stdout.write('\r'+' '*79+'\r'+self.kbbuf.getvalue())
        def AcceptCommand(self, c):
            self.stdout.write('\r>>> '+c+'\n')
            LOG.write('>>> '+c+'\n')
            try:
                self.onecmd(c)
            except Exception, e:
                print 'Error occured during command:'
                traceback.print_exc()
        def precmd(self, line):
            #Remove comments
            #TODO: This implementation is dumb--we should make sure that this character
            #isn't escaped in any way by shlex.
            return line.partition('#')[0]

if __name__=='__main__':
    #Kick off a server!
    print 'Good morning!', SERVER
    if curses:
        print 'Loading the curses environment...'
        print '(You are using the', os.environ['TERM'], 'terminal)'
        #env=CursesConsoleHTTPEnvironment()
        print '(Just kidding, falling back to basic pending further bugfixes...)'
        env=ConsoleHTTPEnvironment()
        env.WriteInfo('Using a curses-based console environment...')
    elif msvcrt:
        print 'Loading the MSVCRT environment...'
        env=MSConsoleHTTPEnvironment()
        env.WriteInfo('Using a MSVCRT-based console environment...')
    else:
        print 'Loading the default (unspecified) environment...'
        env=ConsoleHTTPEnvironment()
    env.onecmd('exec autoexec.txt')
    server=HTTPServer(env, ('', 80))
    while RUNNING:
        time.sleep(1) #Nothing left for the main thread to do...
    print 'Main thread: exiting, goodbye...'
