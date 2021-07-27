import json
import traceback
from binance_api import *
from datetime import datetime, timedelta


# Class to manage a DCA strategy
class DCA:
	def __init__(self):
		self.crypto_amounts = {}
		self.hold_coin = 'USDT'
		self.previous_buys = {}


	# Start a dca 
	def start_dca(self, ):


	# Buy the coin
	def buy(self, coin, amount):


	# Get DCA report for all coins
	def report(self):


	# Save it so it can be resumed
	def save_progress(self):






