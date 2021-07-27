import json
import traceback
from binance_api import *
from datetime import datetime, timedelta
import threading


# Class to manage a DCA strategy
class DCA:

	def __init__(self, name='dca_1'):

		self.crypto_amounts = {}
		self.hold_coin = 'USDT'
		self.previous_buys = {}
		self.wakeup_event = threading.Event()
		self.running_dcas = {}
		sefl.dca_name = name


	# Manage dcas
	def manage_dcas(self):
		self.wakeup_event.wait()
		print('woken up from wakeup')


	# Start a dca 
	def add_dca(self, coin, amount, frequency, start_time=None):

		datetime.now()
		self.buy(coin, amount)

		

	# Buy the coin
	def buy(self, coin, amount):
		print('execute_buy')


	# Get DCA report for all coins
	def report(self):
		for k,v in self.running_dcas.items():
			print(k,v)

	# Stop
	def stop(self):
		print('Stopped')


	# Save it so it can be resumed
	def save(self):
		with open('%s.json', 'a') as json_file:
			json.dump(self.running_dcas)

	
	# Thread asking user for their inputs to interact with the system
	def input_thread(self):
		user_input = input('start, pnl, new, stop, save')	

		if user_input == 'new':
			coin = input('\nChoose coin to buy\n\n')
			amount = input('\nChoose $Amount ot buy\n\n')
			frequency = input('\nChoose frequency to buy\n\n')
			self.add_dca(coin, amount, frequency)
			

		elif user_input == 'stop':
			self.stop()
			

		elif user_input == 'save':
			self.save()

dca = DCA()


(target=dca.input_thread).start()




