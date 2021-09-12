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
from pprint import pprint
from binance_api import *
from ftx_api import *
from kraken_api import *


"""
Class to manage a DCA strategy
"""
class DCA:

	def __init__(self, name='dca_1', simulate=True, log=False):

		self.crypto_amounts = {}
		self.hold_coin = 'USDT'
		self.previous_buys = {}
		self.wakeup_event = threading.Event()
		self.dca_name = name
		self.simulate = simulate
		self.wakeup_times = [] # [[datetime1, coin1], [datetime2, coin2]]
		self.strategies = {'r':lambda x : x, 'f':self.fear_greed}
		self.dca_dict = {}
		self.start_time = datetime.now()
		self.log = log
		self.fg_pull = None
		self.current_prompt = ''
		self.exchange_apis = {'binance':binance_api, 'ftx':ftx_api, 'api':kraken_api}
		self.exchange_dict = {'b':{'api':binance_api,'hold':'USDT', 'name':'binance'}, 'f':{'api':ftx_api, 'hold':'USD', 'name':'ftx'}, 'k': {'api':kraken_api, 'hold':'USD','name':'kraken'}}
		self.save_keys = ['dca_name','crypto_amounts','hold_coin','previous_buys','simulate','wakeup_times','dca_dict','start_time','log','exchange_name']

		with open('../keys.json', 'r') as json_file:
			self.api_keys = json.load(json_file)
			

	"""
	Manage dca in a loop with an event to wakeup to buy
	"""
	def manage_dcas(self):

		sleeptime = None

		while 1:
			try:
				self.wakeup_event.clear()
				self.wakeup_event.wait(timeout=None if not sleeptime else max(0, sleeptime))
				t, coin = self.wakeup_times.pop(0)

				# Clear the previous input prompt text and bring it to the bottom
				for i in range(self.current_prompt.count('\n') + 1):
					sys.stdout.write('\x1b[1A')
					sys.stdout.write('\x1b[2K')

				print('\n\n%s Woken up %s' % ('*'*28, '*'*28))
				if t < datetime.now():
					# Execute the buy
					amount = self.dca_dict[coin]['function']['func'](self.dca_dict[coin]['amount'])

					print('Buying $%.2f' % (amount))
					self.buy(coin, amount)	
					next_buy = datetime.now() + timedelta(seconds=self.dca_dict[coin]['frequency'])

				else:
					# Just add next buy time
					next_buy = t

				print('\nNext buy of %s %s' % (coin, next_buy.strftime('%b %d %H:%M:%S')))
				self.wakeup_times.append([next_buy, coin])

				self.wakeup_times.sort()
				
				if self.wakeup_times[0][0] > datetime.now():
					sleeptime = (self.wakeup_times[0][0] - datetime.now()).total_seconds()
				else:
					sleeptime = 0.1

				print('%s  Sleeping for: %.2fs  %s\n\n %s' % ('-'*20, sleeptime, '-'*20, self.current_prompt))
				"""
				print('Current DCAs:')
				self.report()
				"""

			except Exception as e:
				print('Error %s' %(traceback.format_exc()))


	"""
	Start a dca 
	"""
	def add_dca(self, coin, amount, frequency, start_time, strategy):

		if coin in self.dca_dict:
			print('%s already executing' % (coin))
		else:
			self.dca_dict[coin] = {'amount':amount, 'frequency':frequency, 'function':{'name':strategy, 'func':self.strategies[strategy]}}
			self.wakeup_times.append([start_time, coin])
			self.wakeup_times.sort()
			self.wakeup_event.set()
		

	"""
	Buy the coin
	"""
	def buy(self, coin, amount):

		ticker = '%s/%s' % (coin, self.hold_coin)
		if self.simulate:
			trade = self.api.simulate_buy(ticker, amount)
		else:
			trade = self.api.buy(ticker, amount)

		if self.log:
			self.save_trade(trade, ticker)

		return trade


	"""
	Pull fear and greed index to invest an increasing amount according to it
	Get the fear and greed index from 0-100 with a mean of approximately 50
	More fear == Better time to buy so buy more, more greed, worse time to buy so buy less
	Essentially a way to increase averaging in over dips
	Based around sentiment, volatility, RSI and other factors
	Returns a number between 0 and 2 to scale the buy amount buy 
	"""
	def fear_greed(self, amount, aggression=1):

		# Check when it was last pulled
		now = datetime.now()
		try:
			if self.fg_pull is None or (self.fg_pull.date() < now.date() and now.hour >= 1) or (self.fg_pull.date() == now.date() and self.fg_pull.hour < 1 and now.hour >= 1):
				fg_dict = requests.get('https://api.alternative.me/fng/?format=json&date_format=uk').json()		
				self.fear_greed_value = int(fg_dict['data'][0]['value'])
				self.fg_pull = datetime.now()
				print('Pulled Fear and Greed index: %d' % (self.fear_greed_value))
			
			fg_weight = -2/(1+np.exp(-0.17*(self.fear_greed_value-50)))+2 # Steep transformation of logistic curve for weighting function
			print('Investment multiplier: %.4f' % (fg_weight))

		except Exception as e:
			fg_weight = 1
			print('Error: %s' % e)
		
		return fg_weight * amount 


	"""
	Get DCA report for all coins
	"""
	def report(self):
		pprint({k:v for k,v in self.__dict__.items() if k in self.save_keys})


	"""
	Stop
	"""
	def stop(self):
		self.save()
		print('Stopped and saved\n\n')
		exit()
	

	"""
	Save
	"""
	def save(self):
		
		# Create a dictionary of relevant information to save
		save_dict = {}
		for key in list(set(self.__dict__.keys()).intersection(self.save_keys)):
			save_dict[key] = self.__dict__[key]

		# Manage dcas
		if self.wakeup_times:
			with open('saved_dca/%s_%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S'), 'sim' if self.simulate else 'live'), 'w') as json_file:
				json.dump(save_obj(save_dict), json_file)
		else:
			print('No DCAs runnint to be saved')
	

	"""
	Resume after stopping
	"""
	def resume(self):

		files = sorted(os.listdir('saved_dca/'))
		if files:
			print('\nReloading from last saved file: %s\n' % files[-1])
			with open('saved_dca/%s' % files[-1], 'r') as json_file:
				dca = json.load(json_file)
		
		# Read in all the fields from the saved json
		self.crypto_amounts = dca['crypto_amounts']
		self.hold_coin = dca['hold_coin']
		self.previous_buys = dca['previous_buys']
		if self.simulate != dca['simulate']:
			self.simulate = False if input('\n\nSimulate or not? y/n') == 'n' else True
		self.dca_dict = dca['dca_dict']
		self.exchange_name = dca['exchange_name']
		self.api = self.exchange_apis[self.exchange_name](self.api_keys)

		# Convert all the saved time strings into datetimes
		self.start_time = datetime.strptime(dca['start_time'], '%Y-%m-%dT%H:%M:%S.%f')
		self.wakeup_times = [[datetime.strptime(i[0],'%Y-%m-%dT%H:%M:%S.%f'), i[1]] for i in dca['wakeup_times']]

		# Loop over the coins in the dca dict and put in the function for the dca multiplier
		for coin in self.dca_dict:
			self.dca_dict[coin]['function']['func'] = self.strategies[self.dca_dict[coin]['function']['name']]

		# Loop and get the missed buys
		for i, (wakeup_time, coin) in enumerate(self.wakeup_times):
			if datetime.now() > wakeup_time:
				missed = (datetime.now() - wakeup_time).seconds // self.dca_dict[coin]['frequency'] + 1
				buy_vol = missed * self.dca_dict[coin]['amount']
				print('\n\nFor %s %d buys were missed $%.2f (unweighted)' % (coin, missed, buy_vol))
				buy_skip = input('\n\nBuy missed trades at current price "1" or skip: "2"\n\n')
				
				if buy_skip == '1':
					# TOEDIT # 
					# Apply the multiplier if any
					trade = self.buy(coin, buy_vol)
				else:
					print('\n\n-----Skipping missed buys-----\n\n')
			else:
				print('\n\n----No %s buys missed-----\n\n' % coin)

			self.wakeup_times[i][0] = datetime.now() + timedelta(seconds = (datetime.now() - wakeup_time).seconds % self.dca_dict[coin]['frequency'])


		self.wakeup_times.sort()
		self.wakeup_event.set()
		

	"""
	Print the stats about the DCAs
	"""
	def stats(self):
		# Amount invested
		# Avg buy price
		print('Stats about the dcas running')


	"""
	Log the trade in a json
	"""
	def save_trade(self, trade, ticker):
		if 'prev_trades' not in os.listdir():
			os.mkdir('prev_trades')
		with open('prev_trades/dca_%s_%s_%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S'), ticker.split('/')[0], 'sim' if self.simulate else 'live'), 'w') as write_file:
			json.dump(trade, write_file)

	"""
	Thread asking user for their inputs to interact with the system
	"""
	def input_thread(self):
		t = threading.Thread(target=self.manage_dcas)
		t.setDaemon(True)
		t.start()

		resume = 'n'
		if len(os.listdir('saved_dca')):
			self.current_prompt = '\nResume saved dca from: %s ? y/n\n' % (datetime.strptime(sorted(os.listdir('saved_dca/'))[-1][:17], '%y_%m_%d-%H_%M_%S').strftime('%b %d %H:%M:%S'))
			resume = input(self.current_prompt)
			

		if resume != 'y':

			self.current_prompt = '\nChoose exchange: binance/ftx/kraken: b/f/k\n\n'
			exchange = input(self.current_prompt)
			if not exchange:
				exchange = 'b'
			self.api = self.exchange_dict[exchange.lower()]['api'](self.api_keys)
			self.hold_coin = self.exchange_dict[exchange.lower()]['hold']
			self.exchange_name = self.exchange_dict[exchange.lower()]['name']

			self.current_prompt = '\nUse %s as the coin you hold in your %s wallet? y/n\n\n' % (self.hold_coin, self.exchange_name)
			hold_usdt = input(self.current_prompt)
			if not hold_usdt:
				hold_usdt = 'y'

			# Change the hold coin here
			if hold_usdt.lower() == 'n':
				self.current_prompt = '\nInput currency/coin wallet used to buy crypto e.g. "USDT" "USD" "GBP"\n\n'
				self.hold_coin = input(self.current_prompt).upper()
				if not self.hold_coin:
					self.hold_coin = 'USDT'

				# Check that there are trading pairs with this coin and  the crypto you are buying

		first = True

		try:
			while 1:
				try:
					# New strategy
					if resume == 'y' and first:
						self.resume()	

					first = False
					self.current_prompt = '\nSelect action:\n\nnew dca: "1"\nstats: "2"\nsave: "3"\nstop: "4"\n\n'
					user_input = input(self.current_prompt)
					if not user_input:
						user_input = '1'

					# Get the coin to buy and verify this market exists on the exchange
					if user_input == '1':
						while 1:
							self.current_prompt = '\nInsert coin to buy e.g. "BTC"\n\n'
							coin = input(self.current_prompt).upper()
							if not coin:
								coin = 'BTC'
							if coin+'/'+self.hold_coin not in self.api.markets:
								print('\n\n%s not found in %s tickers' % (coin+'/'+self.hold_coin, self.exchange_name))
							else:
								break

						# Get the average amount to purchase per buy	
						self.current_prompt = '\nInsert $Amount to buy e.g. "10"\n\n'
						amount = input(self.current_prompt)
						if not amount:
							amount = 10
						else:
							amount = float(amount)

						# Get the frequency of the purchases
						self.current_prompt = '\nInsert frequency to buy in Weeks/Days/Hours/Minutes/Seconds W/D/H/M/S\n\ne.g. 20S/12H/3D/1W\n\n'
						freq_str = input(self.current_prompt)
						if not freq_str:
							frequency = 10
							frequency_scale = 's'
						else:
							frequency = float(freq_str[:-1])
							frequency_scale = freq_str[-1]

						# Convert the user input in to a number of seconds to sleep for 
						if frequency_scale.lower() == 'w':
							frequency *= 3600 * 24 * 7
						elif frequency_scale.lower() == 'd':
							frequency *= 3600 * 24
						elif frequency_scale.lower() == 'h':
							frequency *= 3600
						elif frequency_scale.lower() == 'm':
							frequency *= 60

						# Choose a starting time for the dca
						self.current_prompt = '\nWhat time do you want to start the buy (00:00 UTC recommended for fear and greed)\nPut in your local time in 24H format e.g. 19:00 or leave blank for start now\n\n'
						buy_time = input(self.current_prompt)


						# Choose which strategy
						self.current_prompt = '\nStrategy: Regular/Fear & Greed r/f\n\n'
						strategy = input(self.current_prompt)
						if not strategy:
							strategy = 'r'

						# Start the dca
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

		except KeyboardInterrupt:
			print('\nHandling keyboard interrupt')

			self.stop()

log, simulate = False, False
if '-l' in sys.argv:
	log = True
	print('\n\nLogging Buys')
if '-s' in sys.argv:
	simulate = True
	print('\n\nSIMULATING')
else:
	print('\n\nLIVE TRADING')


dca = DCA('dca_test', simulate=simulate, log=log)
dca.input_thread()


