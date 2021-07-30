import json
import traceback
from binance_api import *
from datetime import datetime, timedelta
import threading


# Class to manage a DCA strategy
class DCA:

	def __init__(self, name='dca_1', simulate=True):

		self.crypto_amounts = {}
		self.hold_coin = 'USDT'
		self.previous_buys = {}
		self.wakeup_event = threading.Event()
		self.running_dcas = {}
		self.dca_name = name
		self.simulate = simulate
		self.wakeup_times = [] # [[datetime1, coin1], [datetime2, coin2]]
		self.dca_dict = {}

		with open('../keys.json', 'r') as json_file:
			self.api_keys = json.load(json_file)
			
		# Keep a list sorted by datetime objects 

		
	"""
	# Sleeping thread which wakes up
	def sleeping_thread(self):

		# This is put into a cancellable sleep for a certain amount of timek

		# Woken up by another one starting or by the minimum sleep time
		sleeptime = None 
		if self.wakeup_time:
			sleeptime = (self.wakeup_time[0][0] - datetime.now()).seconds
		self.wakeup_event.wait(timeout=sleeptime)
	"""
		

	# Manage dcas
	def manage_dcas(self):

		print('Managing dcas')
		sleeptime = None
		while 1:

			self.wakeup_event.clear()
			self.wakeup_event.wait(timeout=None if not sleeptime else max(0, sleeptime))
			print('Popped from wakeup')
			t, coin = self.wakeup_times.pop(0)

			print('Woken up from wakeup')
			amount = self.dca_dict[coin]['amount']
			self.buy(coin, amount)	

			self.dca_dict[coin]['next_buy'] = datetime.now() + timedelta(seconds=self.dca_dict[coin]['frequency'])
			print(self.dca_dict[coin]['next_buy'].strftime('%b %d %H:%M:%S'))
			self.wakeup_times.append([self.dca_dict[coin]['next_buy'], coin])
			print(self.wakeup_times)

			self.wakeup_times.sort()

			sleeptime = (self.wakeup_times[0][0] - datetime.now()).seconds

			print(sleeptime)


				

	# Start a dca 
	def add_dca(self, coin, amount, frequency, start_time=datetime.now()):

		if coin in self.dca_dict:
			print('%s already executing' % (coin))
		else:
			self.dca_dict[coin] = {'amount':amount, 'frequency':frequency, 'next_buy':start_time}
			self.wakeup_times.append([start_time, coin])
			self.wakeup_event.set()
		

	# Buy the coin
	def buy(self, coin, amount):

		api = binance_api(self.api_keys)
		ticker = '%s/%s' % (coin, self.hold_coin)

		if self.simulate:
			api.simulate_buy(ticker, amount)
		else:
			api.buy(ticker, amount)

		print('execute_buy')


	# Get DCA report for all coins
	def report(self):
		for k,v in self.running_dcas.items():
			print(k,v)

	# Stop
	def stop(self):
		print('Stopped but can be resumed again')
		self.save()
		exit()


	# Save it so it can be resumed
	def save(self):
		with open('%s.json', 'a') as json_file:
			json.dump(self.running_dcas)

	
	# Thread asking user for their inputs to interact with the system
	def input_thread(self):
		t = threading.Thread(target=self.manage_dcas)
		t.setDaemon(True)
		t.start()
		while 1:
			user_input = input('new, pnl, stop, save\n\n')	

			if user_input == 'new':
				coin = input('\nChoose coin to buy\n\n')
				amount = float(input('\nChoose $Amount to buy\n\n'))
				frequency = float(input('\nChoose frequency to buy\n\n'))

				frequency_scale = input('\nHours/Minutes/Seconds H/M/S\n\n')
				if frequency_scale.lower() == 'h':
					frequency *= 3600
				elif frequency_scale.lower() == 'm':
					frequency *= 60
				print (frequency)
				#buy_time = input('\nSet buy time?\n\n')
				self.add_dca(coin, amount, frequency)

				
			elif user_input == 'stop':
				self.stop()
				
			elif user_input == 'save':
				self.save()

dca = DCA('dca_test', simulate=True)
dca.input_thread()

