import sqlite3

db=sqlite3.connect('master.db')
cur=db.cursor()

class DBObject(object):
	def __init__(self, *data):
		data=list(data)
		if data:
			self.row=data.pop(0)
		else:
			self.row=None
		for fname, default in self.__fields__.itervalues():
			if data:
				v=data.pop(0)
			else:
				v=default
			setattr(self, fname, v)
	def Update(self):
		if self.row:
			cur.execute('UPDATE %(table)s SET %(fields)s WHERE row=?'%{'table': self.__table__, 'fields': ','.join((i+'=?' for i in self.__fields__.keys()))},
					(tuple((getattr(self, i) for i in self.__fields__.keys()))+(self.row,)))
		else:
			cur.execute('INSERT INTO %(table)s (%(fields)s) VALUES (%(marks)s)'%{'table': self.__table__, 'fields': ','.join(self.__fields__.keys()), 'marks': ','.join(['?']*len(self.__fields__))}, tuple((getattr(self, ) for i in self.__fields__.keys())))
			self.row=cur.lastrowid
