from __future__ import unicode_literals
from lib import CoinexPerpetualApi
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)
http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=1, read=2))
import hashlib
from flask import Flask, jsonify, request, render_template
import requests
import time

app = Flask(__name__)




#-----------------------get balance before processing requests

# @app.before_request
def isvalidpswd(pswd):
    with open('passwords.txt', 'r') as file:
        for line in file:
            stored_passwords = line.strip()
            if stored_passwords == pswd:
                return 'True'
    return 'False'

def positionsize(stop_dist, risk_amt):
    positionsize = risk_amt/stop_dist    # formula for position size: position_size = risk_amount/stoploss_distance
    return positionsize

#---------------------get signature for spot ---------------------{

def get_sign(params, secret_key):
    sort_params = sorted(params)
    data = []
    for item in sort_params:
        data.append(item + '=' + str(params[item]))
    str_params = u"{0}&secret_key={1}".format('&'.join(data), secret_key)
    token = hashlib.md5(str_params.encode()).hexdigest().upper()
    return token

#----------------------}

@app.route('/', methods = ['GET'])
def welcome():
    return render_template('index.html')

@app.route('/get_balance', methods=['GET'])
def get_balance(currency = 'USDT'):
    timing = int(time.time() * 1000)
    payload = {
        'tonce': timing,
        'access_id': 'D9BD7B07B4404BC685DE8C5F3CF0546A',
    }
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36'
    }
    headers['AUTHORIZATION'] = get_sign(payload, '88DE926CADA12D0372148B5B1733A76987305CEB5185722A')
    url = 'https://api.coinex.com/v1/balance/info'
    response = requests.get(url, params=payload, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return jsonify({"error": "Failed to fetch balance data"}), 500



@app.route('/webhook', methods=['POST'])
def execution():
    data = request.json
    id = str(data.get('access_id'))
    key = str(data.get('secret_key'))
    symbol = str(data.get('symbol')).upper()
    password = data.get('password')
    bot = CoinexPerpetualApi(id, key)

    if data.get('signal') == 'entry':
        balance_usdt = float(bot.query_account()['data']['USDT']['available'])
        stop_distance = float(data.get('stop_distance'))
        margin_type = str(data.get('margin_type')).upper()
        position = data.get('position')
        risk_pct = (float(str(data.get('risk_percentage'))) * 0.01)
        stop_loss = float(str(data.get('stop_loss')))
        take_profit = float(str(data.get('stop_loss')))
        leverage_recieved = float(str(data.get('leverage')))
        position_type = 2 if position.upper() == 'LONG' else 1
        risk_amount = balance_usdt * risk_pct
        quantity = positionsize(stop_distance, risk_amount)



    def adjust_leverage():
        if leverage_recieved != 0:
            return bot.adjust_leverage(symbol, 1 if margin_type == 'ISOLATED' else 2, leverage_recieved)
    
    def entry():
        adjust_leverage()
        
        bot.put_market_order(symbol, position_type, quantity)
        time.sleep(0.05)

        position_info = bot.query_user_deals(symbol, 0, 1, 0)
        position_id = float(str(position_info['data']['records'][0]['position_id']))
        entry_price = float(str(position_info['data']['records'][0]['open_price']))
        stop_loss_price = entry_price + stop_loss if position_type == 1 else entry_price - stop_loss
        take_profit_price = entry_price + take_profit if position_type == 2 else entry_price - take_profit if take_profit != 0 else 0
        return [position_id, stop_loss_price, take_profit_price]

    def set_exits(position_id, stop_loss_price, take_profit_price):
        bot.adjust_stopLoss(symbol, 3, position_id, stop_loss_price)
        bot.adjust_takeProfit(symbol, 3, position_id, take_profit_price)

        
    def exit_function():
        position_info = bot.query_user_deals(symbol, 0, 1, 0)
        position_id = float(str(position_info['data']['records'][0]['position_id']))
        return jsonify(bot.close_market(symbol, int(position_id)), f'position id: {position_id}')
    
    
    if data.get('signal') == 'entry' and isvalidpswd(password) == 'True':
        trade = entry()
        time.sleep(0.05)
        set_exits(trade[0], trade[1], trade[2])
        position_info = bot.query_user_deals(symbol, 0, 1, 0)
        position_id = float(str(position_info['data']['records'][0]['position_id']))
        entry_price = float(str(position_info['data']['records'][0]['open_price']))        
        return f'trade executed || quantity = {quantity} || entry price = {entry_price} || position id = {position_id}'
    
    if data.get('signal') != 'exit':
        exit_function()
        return exit_function()


@app.route('/getbal', methods = ['POST'])
def getbal():
    data = request.json
    id = str(data.get('access_id'))
    key = str(data.get('secret_key'))
    bot = CoinexPerpetualApi(id, key)
    return str(bot.query_account()['data']['USDT']['available'])

if __name__ == '__main__':
    app.run(debug=True)