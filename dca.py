import json
import threading
import logging
import traceback


# A class to manage DCA's over time
class DCA_manager:

	def __init__(self):
		self.active_dcas = {}
		self.user = User(None, None, None, None)
		self.exchanges_to_use = {'binance'}
		self.logger = logging.getLogger(__name__)
		self.hold_coins = ['USDT']
		self.price_update_interval = 10000
		self.queued_dca = []

		# Load the keys for quanting this dca strategy up
		# TOEDIT # Use different keys for this one
		with open('../../binance_global_read_quant_keys.json') as json_file:
			binance_keys = json.load(json_file)['binance_keys']

		self.exchanges_global = {}
		if 'binance' in self.exchanges_to_use:
			self.binance_exchange = exchange_api({'api_key':binance_keys['api_key'],'secret_key':binance_keys['secret_key']}, self.logger, exchange_name='binance')
			self.binance_global = exchange_pull(self.binance_exchange, self.hold_coins, logger=self.logger, base='USDT', exchange_name='binance', sleep_interval=self.price_update_interval)
			self.exchanges_global['binance'] = self.binance_exchange.prices = self.binance_global

		t = threading.Thread(target=self.binance_global.pull_prices)
		t.start()

	# Start the frequency from 
	def start_dca(self, coin, hold_coin, dollar_amount, frequency=24):

		self.queued_dca.append({'buy_coin':coin, 'hold_coin':hold_coin, 'amount':dollar_amount, 'frequency':frequency, 'started_at':datetime.now()})
		try:
			self.execute_buy(coin, hold_coin, dollar_amount)
		except Exception as e:
			self.logger.error('What is this error %s' %(traceback.format_exc()))
		self.logger.info('starting DCA for %s/%s every %d hours' % (coin, hold_coin, frequency))
		

	# Execute a single buy
	def execute_buy(self, coin, hold_coin, dollar_amount):		

		volume = self.exchanges_global['binance'].buy_sell_volumes(dollar_amount, coin, hold_coin)
		buy_volume = dollar_amount
		exchange = user.link_exchange('binance', simulate=False, prices=self.exchanges_global['binance'])
		exchange.market_buy([coin, hold_coin], dollar_amount)		

		# TOEDIT # report price
		self.logger.info('Market buy the dca')

		
	# Get a report of the average buy price, the amount invested, the amount left for your dca strategies
	def get_report(self,):
		pass


	def weighting(self, ):
		pass


	def change_params(self, ):
		pass


	def calculate_fees(self, ):
		pass


	def log_buy(self, ):
		pass


DCA = DCA_manager()

time.sleep(10)
DCA.start_dca('BTC', 'USDT', 15)









