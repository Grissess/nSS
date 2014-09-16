#neXus portal system
#(no, this is not a video game)

import sqlite3
import base64

#We put this here because the neXus portal system
#is fairly far removed from normal neXus convention
#(which would necessitate putting this in the const
#module).

PORTAL_FILE='portalstate.db'

class State(object):
    def __init__(self, portal, uid, states=None):
        self.portal=portal
        self.uid=uid
        self.states={}
        if states is not None:
            for kv in states.split(','):
                key, val=kv.split('=')
                key, val=base64.b64decode(key), base64.b64decode(val)
                self.states[key]=val
    def Dump(self):
        states=[]
        for key, val in self.states.itervalues():
            states.append(base64.b64encode(key)+'='+base64.b64encode(val))
        return self.portal, self.uid, ','.join(states)
                

class PortalStateDBMan(object):
    def __init__(self, fname=PORTAL_FILE):
        self.con=sqlite3.connect(fname)
    def SetState(self, state):
        