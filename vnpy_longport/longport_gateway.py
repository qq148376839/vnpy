"""
长桥交易接口
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from vnpy.event import EventEngine
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData, OrderData, TradeData, PositionData,
    AccountData, ContractData, BarData, OrderRequest,
    CancelRequest, SubscribeRequest, HistoryRequest
)
from vnpy.trader.constant import (
    Exchange, Product, OrderType, Direction, Status, Interval
)
from vnpy.trader.utility import get_file_path

from longport.openapi import (
    Config, QuoteContext, TradeContext,
    SubType, PushQuote, OrderType as LongPortOrderType,
    OrderSide, TimeInForceType, Period, AdjustType
)


class LongPortGateway(BaseGateway):
    """长桥交易接口"""
    
    default_name: str = "LONGPORT"
    
    default_setting: dict = {
        "app_key": "",
        "app_secret": "",
        "access_token": ""
    }
    
    exchanges: list[str] = [Exchange.SEHK.value, Exchange.NYSE.value]
    
    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        """构造函数"""
        super().__init__(event_engine, gateway_name)
        
        self.quote_ctx: Optional[QuoteContext] = None
        self.trade_ctx: Optional[TradeContext] = None
        
        self.ticks: dict[str, TickData] = {}
        self.orders: dict[str, OrderData] = {}
        self.accounts: dict[str, AccountData] = {}
        self.contracts: dict[str, ContractData] = {}
        
    def connect(self, setting: dict) -> None:
        """连接接口"""
        try:
            # 设置环境变量
            import os
            os.environ["LONGPORT_APP_KEY"] = setting["app_key"]
            os.environ["LONGPORT_APP_SECRET"] = setting["app_secret"]
            os.environ["LONGPORT_ACCESS_TOKEN"] = setting["access_token"]
            
            # 从环境变量加载配置
            config = Config.from_env()
            
            # 创建行情和交易上下文
            self.quote_ctx = QuoteContext(config)
            self.trade_ctx = TradeContext(config)
            
            # 设置回调函数
            self.quote_ctx.set_on_quote(self.on_quote)
            
            self.write_log("长桥接口连接成功")
            
        except Exception as e:
            self.write_log(f"长桥接口连接失败：{str(e)}")
            
    def close(self) -> None:
        """关闭接口"""
        if self.quote_ctx:
            self.quote_ctx.close()
        if self.trade_ctx:
            self.trade_ctx.close()
            
    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        if not self.quote_ctx:
            return
            
        # 转换合约代码格式
        symbol = self._convert_symbol(req.symbol, req.exchange)
        
        # 订阅行情
        self.quote_ctx.subscribe([symbol], [SubType.Quote])
        
        # 创建tick对象
        tick = TickData(
            symbol=req.symbol,
            exchange=req.exchange,
            datetime=datetime.now(),
            gateway_name=self.gateway_name
        )
        self.ticks[symbol] = tick
        
    def send_order(self, req: OrderRequest) -> str:
        """委托下单"""
        if not self.trade_ctx:
            return ""
            
        # 转换合约代码
        symbol = self._convert_symbol(req.symbol, req.exchange)
        
        # 转换订单类型
        order_type = self._convert_order_type(req.type)
        
        # 转换买卖方向
        side = self._convert_direction(req.direction)
        
        try:
            # 发送订单
            resp = self.trade_ctx.submit_order(
                symbol,
                order_type,
                side,
                Decimal(str(req.volume)),
                TimeInForceType.Day,
                submitted_price=Decimal(str(req.price))
            )
            
            # 创建订单对象
            order = OrderData(
                symbol=req.symbol,
                exchange=req.exchange,
                orderid=resp.order_id,
                type=req.type,
                direction=req.direction,
                price=req.price,
                volume=req.volume,
                status=Status.SUBMITTING,
                datetime=datetime.now(),
                gateway_name=self.gateway_name
            )
            
            self.orders[resp.order_id] = order
            self.on_order(order)
            
            return order.vt_orderid
            
        except Exception as e:
            self.write_log(f"委托下单失败：{str(e)}")
            return ""
        
    def cancel_order(self, req: CancelRequest) -> None:
        """委托撤单"""
        if not self.trade_ctx:
            return
            
        try:
            self.trade_ctx.cancel_order(req.orderid)
        except Exception as e:
            self.write_log(f"委托撤单失败：{str(e)}")
        
    def query_account(self) -> None:
        """查询资金"""
        if not self.trade_ctx:
            self.write_log("查询资金失败：交易上下文未初始化")
            return
            
        try:
            # 获取账户信息
            self.write_log("开始获取账户信息...")
            accounts = self.trade_ctx.account_balance()
            self.write_log(f"获取到账户信息：{accounts}")
            
            if not accounts:
                self.write_log("未获取到账户信息")
                return
                
            # 取第一个账户
            account = accounts[0]
            
            # 遍历所有币种的现金信息
            for cash_info in account.cash_infos:
                # 创建资金对象
                account_data = AccountData(
                    accountid=cash_info.currency,
                    balance=float(cash_info.withdraw_cash),
                    frozen=float(cash_info.frozen_cash),
                    gateway_name=self.gateway_name
                )
                
                self.write_log(f"创建资金对象：{account_data}")
                self.on_account(account_data)
                self.write_log("资金对象已发送到事件引擎")
            
        except Exception as e:
            self.write_log(f"查询资金失败：{str(e)}")
        
    def query_position(self) -> None:
        """查询持仓"""
        if not self.trade_ctx:
            self.write_log("查询持仓失败：交易上下文未初始化")
            return
            
        try:
            # 获取持仓信息
            self.write_log("开始获取持仓信息...")
            positions = self.trade_ctx.stock_positions()
            self.write_log(f"获取到持仓信息：{positions}")
            
            # 遍历所有通道
            for channel in positions.channels:
                # 遍历通道中的持仓
                for pos in channel.positions:
                    position = PositionData(
                        symbol=pos.symbol,
                        exchange=self._get_exchange(pos.symbol),
                        direction=Direction.LONG,
                        volume=float(pos.quantity),
                        price=float(pos.avg_cost),
                        pnl=float(pos.unrealized_pnl),
                        gateway_name=self.gateway_name
                    )
                    
                    self.write_log(f"创建持仓对象：{position}")
                    self.on_position(position)
                    self.write_log("持仓对象已发送到事件引擎")
                
        except Exception as e:
            self.write_log(f"查询持仓失败：{str(e)}")
        
    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """查询历史数据"""
        if not self.quote_ctx:
            self.write_log("查询历史数据失败：行情上下文未初始化")
            return []
            
        try:
            # 转换合约代码
            symbol = self._convert_symbol(req.symbol, req.exchange)
            self.write_log(f"转换后的合约代码：{symbol}")
            
            # 转换时间周期
            period = self._convert_interval(req.interval)
            self.write_log(f"转换后的时间周期：{period}")
            
            # 计算需要获取的K线数量
            count = 100  # 默认获取100根K线
            
            # 获取历史数据
            self.write_log("开始获取历史数据...")
            bars = self.quote_ctx.candlesticks(
                symbol,
                period,
                count,
                AdjustType.NoAdjust
            )
            self.write_log(f"获取到历史数据：{bars}")
            
            # 转换数据格式
            result = []
            for bar in bars:
                bar_data = BarData(
                    symbol=req.symbol,
                    exchange=req.exchange,
                    datetime=bar.timestamp,
                    interval=req.interval,
                    open_price=float(bar.open),
                    high_price=float(bar.high),
                    low_price=float(bar.low),
                    close_price=float(bar.close),
                    volume=float(bar.volume),
                    gateway_name=self.gateway_name
                )
                result.append(bar_data)
                
            self.write_log(f"转换后的历史数据：{result}")
            return result
            
        except Exception as e:
            self.write_log(f"查询历史数据失败：{str(e)}")
            return []
        
    def on_quote(self, symbol: str, event: PushQuote) -> None:
        """行情推送回调"""
        tick = self.ticks.get(symbol)
        if not tick:
            return
            
        # 更新tick数据
        tick.last_price = float(event.last_done)
        tick.volume = float(event.volume)
        tick.open_price = float(event.open)
        tick.high_price = float(event.high)
        tick.low_price = float(event.low)
        tick.pre_close = float(event.prev_close)
        tick.datetime = datetime.now()
        
        self.on_tick(tick)
        
    def _convert_symbol(self, symbol: str, exchange: Exchange) -> str:
        """转换合约代码格式"""
        if exchange == Exchange.SEHK:
            return f"{symbol}.HK"
        elif exchange == Exchange.NYSE:
            return f"{symbol}.US"
        return symbol
        
    def _convert_order_type(self, order_type: OrderType) -> LongPortOrderType:
        """转换订单类型"""
        if order_type == OrderType.LIMIT:
            return LongPortOrderType.LO
        elif order_type == OrderType.MARKET:
            return LongPortOrderType.MO
        return LongPortOrderType.LO
        
    def _convert_direction(self, direction: Direction) -> OrderSide:
        """转换买卖方向"""
        if direction == Direction.LONG:
            return OrderSide.Buy
        elif direction == Direction.SHORT:
            return OrderSide.Sell
        return OrderSide.Buy
        
    def _convert_interval(self, interval: Interval) -> Period:
        """转换时间周期"""
        if interval == Interval.MINUTE:
            return Period.Min1
        elif interval == Interval.HOUR:
            return Period.Hour1
        elif interval == Interval.DAILY:
            return Period.Day
        return Period.Day
        
    def _get_exchange(self, symbol: str) -> Exchange:
        """根据合约代码获取交易所"""
        if symbol.endswith(".HK"):
            return Exchange.SEHK
        elif symbol.endswith(".US"):
            return Exchange.NYSE
        return Exchange.SEHK 