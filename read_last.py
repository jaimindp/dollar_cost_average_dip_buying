import os
import json
from pprint import pprint

print(len(os.listdir('saved_dca')))

files = sorted(os.listdir('saved_dca/'))
if files:
	print('\nReloading from last saved file: %s\n' % files[-1])

	with open('saved_dca/%s' % files[-1], 'r') as json_file:
		dca = json.load(json_file)
		pprint(dca)
