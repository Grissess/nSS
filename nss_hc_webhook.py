#Listener for webhook messages from HipChat

import nss
import hypchat
import json

#SENSITIVE INFORMATION: Personal key
hc=hypchat.HypChat('6gHVzFsQA5wiZOkbeSFZiG0KKlL5tOL4Fa3UKnVr')
rm=hc.get_room('Tech Nerd Chat')

class EchoManager(nss.HTTPManager):
	def Handle(self, client, req, server):
		#print req.payload
		try:
			obj=json.loads(req.payload)
		except ValueError:
			raise nss.HTTPError(500, 'No JSON data present')
		rm.notification('<'+obj['item']['room']['name']+'> '+obj['item']['message']['message'], format='text')
		return nss.HTTPResponse('', 204)
