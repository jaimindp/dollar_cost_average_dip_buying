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
from apis.binance_api import *
from apis.ftx_api import *
from apis.kraken_api import *


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
		self.strategies = {'r':{'func':lambda x : x,'name':'regular dca'}, 'f':{'func':self.fear_greed, 'name':'fear_greed'}}
		self.dca_dict = {}
		self.start_time = datetime.now()
		self.log = log
		self.fg_pull = None
		self.current_prompt = ''
		self.exchange_apis = {'binance':binance_api, 'ftx':ftx_api, 'kraken':kraken_api}
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
				for i in range(self.current_prompt.count('\n')):
					sys.stdout.write('\x1b[1A')
					sys.stdout.write('\x1b[2K')

				print('\n\n%s Woken up %s %s\n' % ('*'*20, datetime.now().strftime('%b %m %H:%M:%S'), '*'*20))
				if t < datetime.now():
					try:
						# Execute the buy
						amount = self.dca_dict[coin]['function']['func'](self.dca_dict[coin]['amount'])

						print('Buying $%.2f' % (amount))
						trade = self.buy(coin, amount)	
						self.previous_buys[coin].append(trade)
						next_buy = t + timedelta(seconds=self.dca_dict[coin]['frequency'])
					except Exception as e:
						print('Error buying %s\n%s\n\nContinuing' % (coin, traceback.format_exc()))

				else:
					# Just add next buy time
					next_buy = t

				print('\nNext buy of %s: %s' % (coin, next_buy.strftime('%b %d %H:%M:%S')))
				self.wakeup_times.append([next_buy, coin])

				self.wakeup_times.sort()
				
				if self.wakeup_times[0][0] > datetime.now():
					sleeptime = (self.wakeup_times[0][0] - datetime.now()).total_seconds()
				else:
					sleeptime = 0.1

				print('\n%s  Sleeping for: %.2fs  %s\n\n %s' % ('-'*20, sleeptime, '-'*20, self.current_prompt))

			except Exception as e:
				print('Error\n\n %s\n\nContinuing' % (traceback.format_exc()))


	"""
	Start a dca and print the parameters
	"""
	def add_dca(self, coin, amount, frequency, start_time, strategy, freq_str):

		if coin in self.dca_dict:
			print('%s Already executing dca with this coin' % (coin))
		else:
			self.dca_dict[coin] = {'amount':amount, 'frequency':frequency, 'start_time':start_time, 'function':{'name':strategy, 'func':self.strategies[strategy]['func']}}
			
			# Print out the strategy
			coin_str = ('Coin', coin)
			amount_str = ('Buy Amount', '$%.2f' % amount)
			freq_str = ('Frequency', freq_str)
			strategy_str = ('Strategy', self.strategies[strategy]['name']) 
			start_str = ('Start Time', start_time.strftime('%b %d - %H:%M:%S'))
			dca_str = '  %s\n  *            DCA PARAMS           *' % ('*'*35)
			dca_str += '\n  * %s:%s *' % (coin_str[0], (' '*(30 - len(coin_str[0]) - len(coin_str[1]))) + coin_str[1])
			dca_str += '\n  * %s:%s *' % (amount_str[0], (' '*(30 - len(amount_str[0]) - len(amount_str[1]))) + amount_str[1])
			dca_str += '\n  * %s:%s *' % (freq_str[0], (' '*(30 - len(freq_str[0]) - len(freq_str[1]))) + freq_str[1])
			dca_str += '\n  * %s:%s *' % (strategy_str[0], (' '*(30 - len(strategy_str[0]) - len(strategy_str[1]))) + strategy_str[1])
			dca_str += '\n  * %s:%s *' % (start_str[0], (' '*(30 - len(start_str[0]) - len(start_str[1]))) + start_str[1])
			dca_str += '\n  %s\n\n' % ('*' * 35)
			print(dca_str)

			self.previous_buys[coin] = []

			# Put the start time in the wakeup_queue and wakeup the event
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
			if 'saved_dca' not in os.listdir():
				os.mkdir('saved_dca')
			with open('saved_dca/%s_%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S'), 'sim' if self.simulate else 'live'), 'w') as json_file:
				json.dump(save_obj(save_dict), json_file)
		else:
			print('No DCAs running to be saved')
	

	"""
	Resume after stopping
	"""
	def resume(self):

		if 'saved_dca' not in os.listdir():
			os.mkdir('saved_dca')
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
			self.simulate = False if input('\n\nSimulate or not? y/n\n\n') == 'n' else True
		self.dca_dict = dca['dca_dict']
		self.exchange_name = dca['exchange_name']
		self.api = self.exchange_apis[self.exchange_name](self.api_keys)

		# Convert all the saved time strings into datetimes
		self.start_time = datetime.strptime(dca['start_time'], '%Y-%m-%dT%H:%M:%S.%f')
		self.wakeup_times = [[datetime.strptime(i[0],'%Y-%m-%dT%H:%M:%S.%f'), i[1]] for i in dca['wakeup_times']]

		# Loop over the coins in the dca dict and put in the function for the dca multiplier
		for coin in self.dca_dict:
			self.dca_dict[coin]['function']['func'] = self.strategies[self.dca_dict[coin]['function']['name']]['func']

		# Loop and get the missed buys
		for i, (wakeup_time, coin) in enumerate(self.wakeup_times):
			if datetime.now() > wakeup_time:
				
				missed = (datetime.now() - wakeup_time).seconds // self.dca_dict[coin]['frequency'] + 1
				buy_vol = self.dca_dict[coin]['function']['func'](missed * self.dca_dict[coin]['amount'])
				print('\n\nFor %s %d buys were missed $%.2f (unweighted)' % (coin, missed, buy_vol))
				buy_skip = input('\n\nBuy missed trades at current price "1" or skip: "2"\n\n')
				
				if buy_skip == '1':
					# TOEDIT # 
					# Apply the multiplier if any
					trade = self.buy(coin, buy_vol)
					self.previous_buys[coin].append(trade)
				else:
					print('\n\n-----Skipping missed buys-----\n\n')
				start_time = datetime.strptime(self.dca_dict[coin]['start_time'], '%Y-%m-%dT%H:%M:%S.%f')
				self.wakeup_times[i][0] = datetime.now() + timedelta(seconds=self.dca_dict[coin]['frequency'] - (datetime.now() - start_time).total_seconds() % self.dca_dict[coin]['frequency'])
			else:
				print('\n\n----No %s buys missed-----\n\n' % coin)

		self.current_prompt = '\nSelect action:\n\nnew dca: "1"\nstats: "2"\nsave: "3"\nstop: "4"\n\n'
		print(self.current_prompt)
		self.wakeup_times.sort()
		self.wakeup_event.set()
		

	"""
	Print the stats about the DCAs
	"""
	def stats(self):

		stat_str = ''
		print('\n\n%s DCA Summary %s\n\nNumber of DCAs running: %d\n' % ('-'*20,'-'*20,len(self.previous_buys)))

		# Loop over the previous trades and calculate the average dca buys
		for coin in self.previous_buys:

			stat_str += coin
			tot_spent, tot_bought = 0, 0
			for trade in self.previous_buys[coin]:
				tot_spent += trade['cost']
				tot_bought += trade['amount']

			if tot_spent > 0:
				avg_buy = tot_spent / tot_bought 

				strategy_str = ('Strategy', self.strategies[self.dca_dict[coin]['function']['name']]['name'])
				spent_str = ('Total Spent', '$%.2f' % (tot_spent))
				bought_str = ('Total Bought', '%.8f %s' % (tot_bought, coin))
				avg_str = ('Avg Buy Price', '%.8f' % (avg_buy))

				
				stat_str += '  %s\n\n' % ('*' * 35)
				stat_str =  '\n  %s\n                  %s               ' % ('*'*35, coin)
				stat_str += '\n  * %s:%s *' % (strategy_str[0], (' '*(30 - len(strategy_str[0]) - len(strategy_str[1]))) + strategy_str[1])
				stat_str += '\n  * %s:%s *' % (spent_str[0], (' '*(30 - len(spent_str[0]) - len(spent_str[1]))) + spent_str[1])
				stat_str += '\n  * %s:%s *' % (bought_str[0], (' '*(30 - len(bought_str[0]) - len(bought_str[1]))) + bought_str[1])
				stat_str += '\n  * %s:%s *' % (avg_str[0], (' '*(30 - len(avg_str[0]) - len(avg_str[1]))) + avg_str[1])
				stat_str += '\n  %s\n\n' % ('*' * 35)

				#print('\n%s Total Spent: $%.2f\nTotal Bought %.8f %s\nAvg Buy Price: %.8f' % (coin, tot_spent, tot_bought, coin, avg_buy))
				print(stat_str)

			else:
				print('\nNo buys for %s\n' % coin)


	"""
	Log the trade in a json
	"""
	def save_trade(self, trade, ticker):
		if 'prev_trades' not in os.listdir():
			os.mkdir('prev_trades')
		with open('prev_trades/dca_%s_%s_%s.json' % (datetime.now().strftime('%y_%m_%d-%H_%M_%S'), ticker.split('/')[0], 'sim' if self.simulate else 'live'), 'w') as write_file:
			json.dump(trade, write_file)


	"""
	Get user inputs to set up a new coin to dca into 
	"""
	def new_dca(self):
		self.current_prompt = '\nInsert coin to buy e.g. "BTC"\n\n'
		while 1:
			coin = input(self.current_prompt).upper()
			if not coin:
				coin = 'BTC'
			if coin+'/'+self.hold_coin not in self.api.markets:
				print('\n\n%s not found in %s tickers' % (coin+'/'+self.hold_coin, self.exchange_name))
			else:
				break

		# Get the average amount to purchase per buy	
		self.current_prompt = '\nInsert $Amount to buy e.g. "10"\n\n'
		while 1:
			amount = input(self.current_prompt)
			if not amount:
				amount = 10
				break
			elif amount.replace('.','').isnumeric():
				amount = float(amount)
				break
			print('\nIncorrect format\n')
			
		# Get the frequency of the purchases
		self.current_prompt = '\nInsert frequency to buy in Seconds/Minutes/Hours/Days/Weeks S/M/H/D/W\n\ne.g. 20S/12H/3D/1W\n\n'
		while 1:
			freq_str = input(self.current_prompt)
			try:
				if not freq_str:
					frequency = 10
					frequency_scale = 's'
					break
				elif freq_str[:-1].isnumeric and freq_str[-1].lower() in ['s','m','h','d','w']:
					frequency = float(freq_str[:-1])
					frequency_scale = freq_str[-1]
					break
				else:
					print('\nIncorrect format\n')
			except Exception as e:
				print('\nIncorrect format\n')
				
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
		self.current_prompt = '\nTime to start the buy (00:01 UTC recommended for fear and greed)\nPut in your local time in 24H format e.g. 19:00 or leave blank for start now\n\n'
		while 1:
			start_time = input(self.current_prompt)
			if start_time:
				try:
					hours,minutes = start_time.split(':')
					start_time = datetime.now().replace(hour=int(hours), minute=int(minutes), second=0)
					if start_time < datetime.now():
						start_time += timedelta(days=1)
					break
				except Exception as e:
					print('\nIncorrect format\n')
					
			else:
				start_time = datetime.now()
				break
		print('Starting buys on: %s' % (start_time.strftime('%b %d - %H:%M:%S')))

		# Choose which strategy
		self.current_prompt = '\nStrategy: Regular/Fear & Greed r/f\n\n'
		strategy = input(self.current_prompt)
		if strategy == 'f':
			strategy = 'f'
		else:
			strategy = 'r'
		
		# Start the dca
		self.add_dca(coin, amount, frequency, start_time, strategy, freq_str)


	"""
	Thread asking user for their inputs to interact with the system
	"""
	def input_thread(self):
		t = threading.Thread(target=self.manage_dcas)
		t.setDaemon(True)
		t.start()

		resume = 'n'
		if 'saved_dca' not in os.listdir():
			os.mkdir('saved_dca')
		if len(os.listdir('saved_dca')):
			self.current_prompt = '\nResume saved dca from: %s ? y/n\n\n' % (datetime.strptime(sorted(os.listdir('saved_dca/'))[-1][:17], '%y_%m_%d-%H_%M_%S').strftime('%b %d %H:%M:%S'))
			resume = input(self.current_prompt)
			

		if resume != 'y':
			while 1:
				self.current_prompt = '\nChoose exchange: binance/ftx/kraken: b/f/k\n\n'
				exchange = input(self.current_prompt)
				try:
					if not exchange:
						exchange = 'b'
					self.api = self.exchange_dict[exchange.lower()]['api'](self.api_keys)
					self.hold_coin = self.exchange_dict[exchange.lower()]['hold']
					self.exchange_name = self.exchange_dict[exchange.lower()]['name']
					break
				except Exception as e:
					print('\nIncorrect entry\n')

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

					# Get the coin to buy and verify this market exists on the exchange
					if user_input in ['1', '']:
						self.new_dca()
					elif user_input == '2':
						self.stats()
					elif user_input == '3':
						self.save()
					elif user_input == '4':
						self.stop()
					else:
						print('\nInvalid response\n')
						
				except Exception as e:
					print('Error in input: %s' % (traceback.format_exc()))
					self.stop()

		except KeyboardInterrupt:
			print('\nHandling keyboard interrupt')
			self.stop()

if __name__ == '__main__':
	log, simulate = False, False
	if '-l' in sys.argv:
		log = True
		print('\n\nLogging Buy Orders')
	if '-s' in sys.argv:
		simulate = True
		print('\n\nSIMULATING')
	else:
		print('\n\nLIVE TRADING')


	dca = DCA('dca_test', simulate=simulate, log=log)
	dca.input_thread()


