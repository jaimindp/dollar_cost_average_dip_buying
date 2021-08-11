import json
import traceback
import requests
from binance_api import *
from datetime import datetime, timedelta
import threading
import numpy as np


# Class to manage a DCA strategy
class DCA:

	def __init__(self, name='dca_1', simulate=True, log=False):

		self.crypto_amounts = {}
		self.hold_coin = 'USDT'
		self.previous_buys = {}
		self.wakeup_event = threading.Event()
		self.running_dcas = {}
		self.dca_name = name
		self.simulate = simulate
		self.wakeup_times = [] # [[datetime1, coin1], [datetime2, coin2]]
		self.strategies = {'r':lambda x : x, 'f':self.fear_greed}
		self.dca_dict = {}
		self.start_time = datetime.now()
		self.log = log
		self.fg_pull = None

		with open('../keys.json', 'r') as json_file:
			self.api_keys = json.load(json_file)
			
		# Keep a list sorted by datetime objects 


	# Manage dcas
	def manage_dcas(self):

		sleeptime = None

		while 1:
			try:
				self.wakeup_event.clear()
				self.wakeup_event.wait(timeout=None if not sleeptime else max(0, sleeptime))
				t, coin = self.wakeup_times.pop(0)

				print('Woken up from sleep')
				amount = self.dca_dict[coin]['function'](self.dca_dict[coin]['amount'])
				print('Amount to buy %.2f' % (amount))
				self.buy(coin, amount)	

				self.dca_dict[coin]['next_buy'] = datetime.now() + timedelta(seconds=self.dca_dict[coin]['frequency'])
				print('Next buy of %s %s' % (coin, self.dca_dict[coin]['next_buy'].strftime('%b %d %H:%M:%S')))
				self.wakeup_times.append([self.dca_dict[coin]['next_buy'], coin])

				self.wakeup_times.sort()
				if self.wakeup_times[0][0] > datetime.now():
					sleeptime = (self.wakeup_times[0][0] - datetime.now()).total_seconds()
				else:
					sleeptime = 0.1

				print('Sleeping for: %ss' % (sleeptime))
			
			except Exception as e:
				print('Error %s' %(traceback.format_exc()))


	# Start a dca 
	def add_dca(self, coin, amount, frequency, start_time, strategy):

		if coin in self.dca_dict:
			print('%s already executing' % (coin))
		else:
			
			self.dca_dict[coin] = {'amount':amount, 'frequency':frequency, 'next_buy':start_time, 'function':self.strategies[strategy]}
			self.wakeup_times.append([start_time, coin])
			self.wakeup_times.sort()
			self.wakeup_event.set()
		

	# Buy the coin
	def buy(self, coin, amount):

		api = binance_api(self.api_keys)
		ticker = '%s/%s' % (coin, self.hold_coin)
		if self.simulate:
			trade = api.simulate_buy(ticker, amount)
		else:
			trade = api.buy(ticker, amount)

		if self.log:
			self.save_trade(trade, ticker)


	# Pull fear and greed index to invest an increasing amount according to it
	# Danger of min buy amounts being lower than executable on exchange (how to combat?)
	def fear_greed(self, amount):
		# Get the fear and greed index from 0-100 with a mean of approximately 50
		# More fear == Better time to buy so buy more, more greed, worse time to buy so buy less
		# Essentially a way to increase averaging in over dips
		# Based around sentiment, RSI and other factors
		# Returns a number between 0 and 2 to scale the buy amount buy 

		# Check when it was last pulled
		now = datetime.now()
		if self.fg_pull is None or (self.fg_pull.date() < now.date() and now.hour >= 1) or (self.fg_pull.date() == now.date() and self.fg_pull.hour < 1 and now.hour >= 1):
			fg_dict = requests.get('https://api.alternative.me/fng/?format=json&date_format=uk').json()		
			self.fear_greed_value = int(fg_dict['data'][0]['value'])
			self.fg_pull = datetime.now()
			print('Just pulled new fear and greed index: %d' % (self.fear_greed_value))
		
		fg_weight = -2/(1+np.exp(-0.17*(self.fear_greed_value-50)))+2 # Steep transformation of logistic curve for weighting function
		print('Multiplier: %.4f' % (fg_weight))
		return fg_weight * amount 


	# Get DCA report for all coins
	def report(self):
		for k,v in self.running_dcas.items():
			print(k,v)


	# Stop
	def stop(self):
		print('Stopped but can be resumed again')


	# Save it so it can be resumed
	def save_trade(self, trade, ticker):
		with open('prev_trades/dca_%s_%s_%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S'), ticker.split('/')[0], 'sim' if self.simulate else 'live'), 'w') as write_file:
			json.dump(trade, write_file)
	

	# Thread asking user for their inputs to interact with the system
	def input_thread(self):
		t = threading.Thread(target=self.manage_dcas)
		t.setDaemon(True)
		t.start()

		while 1:

			try:
				user_input = input('\n\nChoose action: new, pnl, stop, save\n\n')	

				if user_input == 'new':
					coin = input('\nChoose coin to buy\n\n').upper()
					amount = float(input('\nChoose $Amount to buy\n\n'))
					frequency = float(input('\nChoose frequency to buy\n\n'))

					frequency_scale = input('\nWeeks/Days/Hours/Minutes/Seconds W/D/H/M/S\n\n')
					if frequency_scale.lower() == 'w':
						frequency *= 3600 * 24 * 7
					elif frequency_scale.lower() == 'd':
						frequency *= 3600 * 24
					elif frequency_scale.lower() == 'h':
						frequency *= 3600
					elif frequency_scale.lower() == 'm':
						frequency *= 60

					strategy = input('\nStrategy: Regular/Fear & Greed r/f\n\n')

					self.add_dca(coin, amount, frequency, datetime.now(), strategy)
					
				elif user_input == 'stop':
					self.stop()
					
				elif user_input == 'save':
					self.save()

				time.sleep(2)

			except Exception as e:
				print('Error in input: %s' % (traceback.format_exc()))
				exit()


log, simulate = False, False
if '-l' in sys.argv:
	log = True
	print('logging')
if '-s' in sys.argv:
	simulate = True
	print('\n\nSIMULATING')
else:
	print('\n\nLIVE TRADING')


dca = DCA('dca_test', simulate=simulate, log=log)
dca.input_thread()


