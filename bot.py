import asyncio,json,os,websockets,aiohttp
DERIV_TOKEN=os.environ.get('DERIV_TOKEN','AsM5Q3tSxWRUqSj')
TELEGRAM_TOKEN=os.environ.get('TELEGRAM_TOKEN','8624357847:AAEbpw4FdQauGATweIJBJqb93ZkAsKmkFW0')
TELEGRAM_CHAT_ID=os.environ.get('TELEGRAM_CHAT_ID','1117206336')
STAKE=5.0;GROWTH_RATE=0.05;TP_PER_TRADE=2.50;DAILY_PROFIT_LIMIT=30.0;DAILY_LOSS_LIMIT=10.0
SYMBOLS=['R_25','R_75','R_100']
NAMES={'R_25':'Vol 25','R_75':'Vol 75','R_100':'Vol 100'}
tick_history={'R_25':[],'R_75':[],'R_100':[]}
daily_pnl=0.0;daily_loss=0.0;in_trade=False;contract_id=None;trade_count=0;running=True
async def tg(msg):
 async with aiohttp.ClientSession() as s:
  await s.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',json={'chat_id':TELEGRAM_CHAT_ID,'text':msg,'parse_mode':'HTML'})
def pattern(sym):
 h=tick_history[sym]
 return len(h)>=2 and 20<=h[-2]<=29 and 20<=h[-1]<=29
async def bot():
 global daily_pnl,daily_loss,in_trade,contract_id,trade_count,running
 while running:
  try:
   async with websockets.connect('wss://ws.binaryws.com/websockets/v3?app_id=1089') as ws:
    await ws.send(json.dumps({'authorize':DERIV_TOKEN}))
    r=json.loads(await ws.recv())
    if r.get('error'):
     await tg('Auth failed: '+r['error']['message']);return
    bal=r['authorize']['balance']
    await tg(f'🤖 Bot Started\nBalance: ${bal:.2f}\nWatching Vol 25, 75, 100\nStake: $5 | Growth: 5%\nDaily target: +$30 | Stop: -$10')
    for s in SYMBOLS:
     await ws.send(json.dumps({'ticks':s,'subscribe':1}))
    async def ping():
     while running:
      await asyncio.sleep(25)
      try:await ws.send(json.dumps({'ping':1}))
      except:break
    asyncio.create_task(ping())
    async for raw in ws:
     msg=json.loads(raw)
     mt=msg.get('msg_type')
     if mt=='proposal_open_contract':
      c=msg.get('proposal_open_contract',{})
      cid=c.get('contract_id');sym=c.get('underlying')
      profit=float(c.get('profit',0));ticks=c.get('tick_count',0) or 0;status=c.get('status')
      if in_trade and cid==contract_id and profit>=TP_PER_TRADE and not c.get('is_sold'):
       await ws.send(json.dumps({'sell':cid,'price':0}))
      if status in('sold','expired') and cid==contract_id:
       in_trade=False;contract_id=None;trade_count+=1
       daily_pnl+=profit
       if profit<0:daily_loss+=abs(profit)
       if sym and ticks>0:
        tick_history[sym].append(ticks)
        if len(tick_history[sym])>30:tick_history[sym].pop(0)
       e='✅' if profit>=0 else '❌'
       await tg(f'{e} Trade Closed\nSymbol: {NAMES.get(sym,sym)}\nTicks: {ticks}\nP&L: ${profit:.2f}\nDaily P&L: ${daily_pnl:.2f}')
       if daily_pnl>=DAILY_PROFIT_LIMIT:
        await tg(f'🎯 Daily target hit! +${daily_pnl:.2f}\nBot stopping.');running=False;break
       if daily_loss>=DAILY_LOSS_LIMIT:
        await tg(f'🛑 Loss limit hit! -${daily_loss:.2f}\nBot stopping.');running=False;break
       if not in_trade and pattern(sym):
        await tg(f'🎯 Pattern! {NAMES.get(sym,sym)}\nLast 2 ticks: {tick_history[sym][-2]}, {tick_history[sym][-1]}\nEntering trade!')
        await ws.send(json.dumps({'buy':1,'price':STAKE,'parameters':{'contract_type':'ACCU','symbol':sym,'currency':'USD','growth_rate':GROWTH_RATE,'basis':'stake','amount':STAKE}}))
     elif mt=='buy':
      b=msg.get('buy')
      if b:
       contract_id=b['contract_id'];in_trade=True
       await ws.send(json.dumps({'proposal_open_contract':1,'contract_id':contract_id,'subscribe':1}))
  except Exception as e:
   print(f'Error:{e}');await asyncio.sleep(5)
asyncio.run(bot())
