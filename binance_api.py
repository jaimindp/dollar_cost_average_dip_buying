import ccxt
import time
from datetime import datetime
import json
import traceback
import os
import sys

# Executes buying and selling
class binance_api:

	# Initialize
	def __init__(self, api_keys):
		self.api_keys = {'api_key':api_keys['binance_keys']['api_key'],'secret_key':api_keys['binance_keys']['secret_key']}
		self.exchange = ccxt.binance({'apiKey':self.api_keys['api_key'], 'secret':self.api_keys['secret_key']})



	def buy(self, ticker, buy_volume):
		mytick = self.exchange.fetch_ticker(ticker)
		price = self.exchange.fetch_ticker(ticker)['ask']
		buy_trade = self.exchange.create_order(ticker,'market','buy',buy_volume)
		self.retrieve_order_fees(buy_trade)
		return buy_trade


	# Get the fees for a trade
	def retrieve_order_fees(self, trade):
		try:
			count = 0
			while (trade['status'] is None or trade['status'] == 'open') and count < 3:
				trade = self.exchange.fetch_order(trade['id'], trade['symbol'])
				count += 1

			# Get the fee from trades
			if trade['fee'] is None:
				trades = self.exchange.fetch_my_trades(trade['symbol'], since=int((datetime.now()-timedelta(seconds=10)).timestamp() * 1000))

				# Loop over from fetch_my_trades to get the fee and timestamp information
				if trades:
					fees = None
					if trades[-1]['fee'] is not None:
						fees = {'cost':0, 'currency':trades[-1]['fee']['currency']}

						# Loop backwards over the trades found
						for individual_trade in trades[::-1]:
							if individual_trade['order'] == trade['id']:
								fees['cost'] += individual_trade['fee']['cost']
							else:
								break
						print('Get trades for %s since fees were not present cost: %s  currency: %s' % (trade['symbol'], fees['cost'], fees['currency']))

					trade['fee'] = fees

					# Changing the timestamp to the last trade timestamp
					if trade['timestamp'] is None:
						trade['timestamp'] = trades[-1]['timestamp']

			return trade
			
		except Exception as e:
			print('Error: fetching trade - %s' % (traceback.format_exc()))


	# Get data from self.exchange and print it 
	def simulate_buy(self, ticker, buy_volume):

		trade_price = self.exchange.fetch_ticker(ticker)['ask']

		print('\n{} at {:.8f} {} = ${:.6f}'.format(buy_volume, trade_price, ticker, trade_price))
		trade = {'symbol':ticker ,'side':'buy', 'amount':buy_volume, 'cost':trade_price * buy_volume}
		
		return trade

