import json
import traceback
import requests
import os
from datetime import datetime, timedelta
import threading
import numpy as np
import sys
import queue
from save import *
from binance_api import *
from ftx_api import *
from kraken_api import *


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
		self.current_prompt = ''
		self.save_keys = ['dca_name','crypto_amounts','hold_coin','previous_buys','running_dcas','simulate','wakeup_times','dca_dict','start_time','log']

		with open('../keys.json', 'r') as json_file:
			self.api_keys = json.load(json_file)
			

	# Manage dcas
	def manage_dcas(self):

		sleeptime = None

		while 1:
			try:
				self.wakeup_event.clear()
				self.wakeup_event.wait(timeout=None if not sleeptime else max(0, sleeptime))
				t, coin = self.wakeup_times.pop(0)

				amount = self.dca_dict[coin]['function']['func'](self.dca_dict[coin]['amount'])
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

				print('Sleeping for: %ss\n\n%s' % (sleeptime, self.current_prompt))
			
			except Exception as e:
				print('Error %s' %(traceback.format_exc()))


	# Start a dca 
	def add_dca(self, coin, amount, frequency, start_time, strategy):

		if coin in self.dca_dict:
			print('%s already executing' % (coin))
		else:
			self.dca_dict[coin] = {'amount':amount, 'frequency':frequency, 'next_buy':start_time, 'function':{'name':strategy, 'func':self.strategies[strategy]}}
			self.wakeup_times.append([start_time, coin])
			self.wakeup_times.sort()
			self.wakeup_event.set()
		

	# Buy the coin
	def buy(self, coin, amount):

		# api = binance_api(self.api_keys)
		# api = ftx_api(self.api_keys)
		ticker = '%s/%s' % (coin, self.hold_coin)
		if self.simulate:
			trade = self.api.simulate_buy(ticker, amount)
		else:
			trade = self.api.buy(ticker, amount)

		if self.log:
			self.save_trade(trade, ticker)


	# Pull fear and greed index to invest an increasing amount according to it
	# Danger of min buy amounts being lower than executable on exchange (how to combat?)
	def fear_greed(self, amount):
		# Get the fear and greed index from 0-100 with a mean of approximately 50
		# More fear == Better time to buy so buy more, more greed, worse time to buy so buy less
		# Essentially a way to increase averaging in over dips
		# Based around sentiment, volatility, RSI and other factors
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

		# Create a dictionary of relevant information to save
		save_dict = {}
		for key in list(set(self.__dict__.keys()).intersection(self.save_keys)):
			save_dict[key] = self.__dict__[key]

		# Manage dcas
		with open('saved_dca/%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S')), 'w') as json_file:
			json.dump(save_obj(save_dict), json_file)

		print('Stopped and saved')
		exit()
	

	# Resume after stopping
	def resume(self):

		files = sorted(os.listdir('saved_dca/'))
		if files:
			input('Is this correct y/n:\n\n%s\n' % files[-1])

			with open('saved_dca/%s' % files[-1], 'r') as json_file:
				dca = json.load(json_file)
		
		self.crypto_amounts = dca['crypto_amounts']
		self.hold_coin = dca['hold_coin']
		self.previous_buys = dca['previous_buys']
		self.running_dcas = dca['previous_buys']
		self.simulate = dca['simulate']
		self.wakeup_times = dca['simulate']
		self.strategies = dca['strategies']
		self.dca_dict = dca['dca_dict']
		self.start_time = dca['start_time']


	# Print the stats about the DCAs
	def stats(self):
		print('Stats about the dcas running')


	# Save it so it can be resumed
	def save_trade(self, trade, ticker):
		with open('prev_trades/dca_%s_%s_%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S'), ticker.split('/')[0], 'sim' if self.simulate else 'live'), 'w') as write_file:
			json.dump(trade, write_file)

	"""
	Thread asking user for their inputs to interact with the system
	"""
	def input_thread(self):
		t = threading.Thread(target=self.manage_dcas)
		t.setDaemon(True)
		t.start()

		exchange_dict = {'b':{'api':binance_api,'hold':'USDT', 'name':'binance'}, 'f':{'api':ftx_api, 'hold':'USD', 'name':'ftx'}, 'k': {'api':kraken_api, 'hold':'USD','name':'kraken'}}
		self.current_prompt = '\nChoose exchange: binance/ftx/kraken: b/f/k\n\n'
		exchange = input(self.current_prompt)
		if not exchange:
			exchange = 'b'
		self.api = exchange_dict[exchange.lower()]['api'](self.api_keys)
		self.hold_coin = exchange_dict[exchange.lower()]['hold']
		self.exchange_name = exchange_dict[exchange.lower()]['name']

		self.current_prompt = '\nUsing %s as the coin you hold in your %s wallet\nDo you want to change this? y/n\n\n' % (self.hold_coin, self.exchange_name)
		change = input(self.current_prompt)
		if not change:
			change = 'n'

		# Change the hold coin here
		if change.lower() == 'y':
			self.current_prompt = '\nInput currency/coin wallet used to buy crypto e.g. "USDT" "USD" "GBP"\n\n'
			self.hold_coin = input(self.current_prompt).upper()
			if not self.hold_coin:
				self.hold_coin = 'USDT'
			# Check that there are trading pairs with this coin and  the crypto you are buying

		first = True

		while 1:
			try:
				self.current_prompt = 'Select action:\n\n%snew dca: "1"\nstats: "2"\nsave: "3"\nstop: "4"\n\n' % ('Resume: "0"\n' if first else '')
				first = False
				user_input = input(self.current_prompt)
				if not user_input:
					user_input = '1'

				# New strategy
				if user_input == '0':
					self.resume()	
				elif user_input == '1':
					self.current_prompt = '\nInsert coin to buy e.g. "BTC"\n\n'
					coin = input(self.current_prompt).upper()
					if not coin:
						coin = 'BTC'

					self.current_prompt = input('\nInsert $Amount to buy e.g. "10"\n\n')
					if not self.current_prompt:
						amount = 10
					else:
						amount = float(self.current_prompt)

					self.current_prompt = input('\nInsert frequency to buy in Weeks/Days/Hours/Minutes/Seconds W/D/H/M/S\n\ne.g. 20S/12H/3D/1W\n\n')
					if not self.current_prompt:
						frequency = 2
						frequency_scale = 's'
					else:
						frequency = float(self.current_prompt[:-1])
						frequency_scale = self.current_prompt[-1]

					# Convert the user input in to a number of seconds to sleep for 
					if frequency_scale.lower() == 'w':
						frequency *= 3600 * 24 * 7
					elif frequency_scale.lower() == 'd':
						frequency *= 3600 * 24
					elif frequency_scale.lower() == 'h':
						frequency *= 3600
					elif frequency_scale.lower() == 'm':
						frequency *= 60

					self.current_prompt = '\nStrategy: Regular/Fear & Greed r/f\n\n'
					strategy = input(self.current_prompt)
					if not strategy:
						strategy = 'r'

					self.add_dca(coin, amount, frequency, datetime.now(), strategy)
					
				# Not yet implemented
				elif user_input == '2':
					self.stats()
				
				# Not yet implemented
				elif user_input == '3':
					self.save()

				# Not yet implemented
				elif user_input == '4':
					self.stop()
					
				#time.sleep(10)

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

