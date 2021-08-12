# Dollar Cost Averaging - Custom parameter DCA (Work in Progress)

Dollar Cost Averaging: Dividing the total amount of money to be invested periodically over time to reduce the impact of volatility on the average buy price. If you think investing in crypto is risky, it's a good risk averse way to get exposed to the market especially in volatile times (Always)

This repository WILL let you run, backtest and speculatively forward-test Dollar Cost Averaging strategies for crypto so you can customise your DCA minimising risk, while maximising profits in a way which suits you

Places market buy orders on the exchange you use in the spot market getting the current price then sleeps until the next buy interval. It will save progress so it doesn't have to be continuously run. Different DCA strategies will be put in as we go!

Strategies tested and planning to be tested:
- According to the Crypto Fear and Greed Index https://alternative.me/crypto/fear-and-greed-index (Buys more when fear is higher, buys less when greed is higher)
- RSI based DCA
- Volatility Based DCA

### Updates
August 12th:
Fear and greed DCA handling for buy amounts lower than the minimum buy amount for each coin

August 8th:
Basic DCA works for all cryptos on Binance, needs to be run permanently 


