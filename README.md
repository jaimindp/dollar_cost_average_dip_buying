# Dollar Cost Averaging - Custom parameter DCA

Dollar Cost Averaging: Dividing the total amount of money to be invested periodically over time to reduce the impact of volatility on the average buy price. If you think investing in crypto is risky, it's a good risk averse way to get exposed to the market especially in volatile times (Always)

This repository lets you run, backtest and speculatively forward-test Dollar Cost Averaging strategies for crypto so you can customise your DCA minimising risk, while maximising profits in a way which suits you

To get started you will need an account from Binance/FTX/Kraken (Fee reducing referral links below):

- [x] Binance: https://accounts.binance.com/en/register?ref=CP1DAOWU 
- [x] FTX: https://ftx.com/#a=33799830 
- [ ] Kraken: https://r.kraken.com/KeJqje


Create API keys with 'trading' permissions enabled and load up your spot wallet with USD or USDT or whatever currency you want to use to buy crypto.

Put your API keys in a json_file called `keys.json`, (Only the keys used to trade need to be included)

```
{
    "binance_keys":{
        "api_key":"XXXXXXXXXXXXXXXXXXXX",
        "secret_key":"XXXXXXXXXXXXXXXXXXXX"
    },
    "ftx_keys":{
        "api_key":"XXXXXXXXXXXXXXXXXXXX",
        "secret_key":"XXXXXXXXXXXXXXXXXXXX"
    },
    "kraken_keys":{
    	"api_key":"XXXXXXXXXXXXXXXXXXXX",
        "secret_key":"XXXXXXXXXXXXXXXXXXXX"
    }
}
```

Install the required python packages using `pip install -r requirements.txt` from the root directory

To start, run `python dca.py` or `python dca.py -s` which will place fake orders (to trial it out).

Places (spot) market buy orders on the exchange at the current price, it then sleeps until the next buy interval. It will save progress so it doesn't have to be continuously run but I would reccomend running this perpetually (on a linux based microcomputer like a Rasberry Pi). Different DCA strategies will be put in as we go!

Strategies tested and planning to be tested:
- [x] According to the Crypto Fear and Greed Index https://alternative.me/crypto/fear-and-greed-index (Buys more when fear is higher, buys less when greed is higher)
- [ ] RSI based DCA
- [ ] Volatility Based DCA

### Updates
August 27th
FTX Set up and more intuitive UI. Also more backtesting in the analysis notbook

August 12th:
Fear and greed DCA handling for buy amounts lower than the minimum buy amount for each coin

August 8th:
Basic DCA works for all cryptos on Binance, needs to be run permanently

