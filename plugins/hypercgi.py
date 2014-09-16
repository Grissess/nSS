#nSS Plugin -- HyperCGI
NAME='HyperCGI'
VER=0x000000A01
S_VER=0x0005A00
LNAME='HyperCGI -- A (very) fast CGI rexec environment that doesn\'t spawn new processes.'
DESC='A CGI environment that runs over the normal nss_fs.CGIFileSystem, running scripts in \
the main thread (or new threads) rather than in new processes. Due to memory sharing afforded by \
this technique, execution time of CGI scripts (written in Python) can be drastically reduced. \
However, the technique is more likely to cause server instability; use with care.'

NOT_PLUGIN=True #Disabled temporarily!

import os
import sys

import cStringIO

import plugin
nss_fs=plugin.LoadSym('nss_fs')

codecache={}

class CGIEnvironment(object):
    def __init__(self, server):
        self.server=server
    def DoRun(self, path, env, client, req):
        self.SetUpEnv(env)
        try:
            return self.RunCGI(path)
        except plugin.nss.HTTPError:
            raise #Pass it on...
        except SystemExit:
            pass #No need to worry...
        except BaseException, e:
            print>>sys.stderr, 'CGI Script at '+path+' exited on error: '+repr(e)
            import traceback
            traceback.print_exc()
        finally:
            self.TearDown()
    def SetUpEnv(self, env):
        fullenv=os.environ.copy()
        self.oldenv=os.environ
        fullenv.update(env)
        os.environ=fullenv
        self.oldstdout=sys.stdout
        sys.stdout=cStringIO.StringIO()
        sys.exitfunc=lambda: None
    def TearDown(self):
        sys.stdout=self.oldstdout
        os.environ=self.oldenv
    def RunCGI(self, path):
        global codecache
        if path not in codecache:
            try:
                codecache[path]=compile(open(path, 'r').read(), path, 'exec')
            except Exception, e:
                print>>sys.stderr, 'Could not compile script at '+path+': '+repr(e)
                import traceback
                traceback.print_exc()
                raise plugin.nss.HTTPError(500, longdesc='Script compile failed.')
        newns={'nss': plugin.nss, '_server': self.server}
        sys.path.append(os.path.split(path)[0])
        exec codecache[path] in newns
        if hasattr(sys, 'exitfunc'):
            sys.exitfunc()
        del sys.path[-1]
        ret=sys.stdout.getvalue() #This stagger may help just in case sys.stdout is no
        return plugin.nss.HTTPRawResponse(ret) #longer a StringIO
    def Hook(self, cgifs):
        cgifs.DoRun=self.DoRun
    def UnHook(self, cgifs):
        del cgifs.DoRun #Should del from __dict__, not type(cgifs).__dict__ (hopefully)
    
class HyperCGIPlugin(plugin.BasePlugin):
    def Load(self, server):
        self.server=server
        self.hooked=[]
        self.cgienv=CGIEnvironment(self.server)
    def Unload(self):
        self.UnloadFrom(self.hooked)
    def LoadFrom(self, mans):
        ret=[]
        for man in mans:
            if isinstance(man, nss_fs.CGIFileSystem):
                self.cgienv.Hook(man)
                ret.append(man)
        return ret
    def UnloadFrom(self, mans):
        for man in mans:
            self.cgienv.UnHook(man)
    def do_reload(self, line):
        '''reload

Reloads HyperCGI. You need to do this after setting up all CGIFileSystems for this to take effect.
Optionally, you can do it after loading only the CGIFS's for which this is needed.
If called after an unloadall (or after all CGIFS's are cleared), HyperCGI is detached from all CGIFS's created thereafter.'''
        self.UnloadFrom(self.hooked)
        self.hooked=self.LoadFrom(plugin.nss.HTTPHandler.MANAGERS)
    def do_unload(self, line):
        '''unload

Unconditionally unloads all CGIFileSystems from HyperCGI.'''
        self.UnloadFrom(self.hooked)
        self.hooked=[]

Plugin=HyperCGIPlugin        