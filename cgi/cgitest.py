#CGI test module

import cgi
import sys

class tee(object):
	def __init__(self, *fds):
		self.fds=fds
	def write(self, data):
		for fd in self.fds:
			fd.write(data)
	def flush(self):
		for fd in self.fds:
			fd.flush()

sys.stdout=tee(sys.stdout, open('../lastreq.html', 'wb'))

print 'HTTP/1.1 200 OK'
cgi.test()
