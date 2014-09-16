#Because why not?

import nss

class FileData(object):
	def __init__(self, name, buf):
		self.name=name
		self.buf=buf

CURDATA=None

class TransferManager(nss.HTTPManager):
	def Handle(self, client, req, server):
		global CURDATA
		if CURDATA is None:
			if 'file' in req.formdata and req.formdata['file'].file:
				CURDATA=FileData(req.formdata['file'].filename, req.formdata['file'].file.read())
				return nss.HTTPResponse('<p>Your file is uploaded.</p>')
			else:
				return nss.HTTPResponse('<form action="?" method="POST" enctype="multipart/form-data"><input type="file" name="file"/><button name="submit" type="submit">Submit</button></form>')
		else:
			data=CURDATA
			CURDATA=None
			return nss.HTTPResponse(data.buf, headers={'Content-Disposition': 'attachment; filename="'+data.name+'"', 'Content-Type': 'application/octet-stream'})
