#nSS Plugin specs

NOT_PLUGIN=True #Tell nSS not to load this as plugin

NAME='Plugin Base Utilities' #Still need this

import sys
import os

def AddNSSImportPath(thenrun):
    sys.path.append(os.path.abspath('..'))
    ret=thenrun()
    del sys.path[-1]
    return ret

def LoadSym(name):
    return AddNSSImportPath(lambda name=name: __import__(name))

nss=LoadSym('nss')

#A Basic Plugin
class BasePlugin(object):
    def Load(self, server):
        pass
    def Unload(self):
        pass
    def Handle(self, man, client, req, server):
        pass
    def FilterResponse(self, client, resp, req):
        return resp