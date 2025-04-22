"""
测试长桥接口
"""

import time
from datetime import datetime, timedelta
from typing import Any

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import (
    SubscribeRequest,
    OrderRequest,
    CancelRequest,
    HistoryRequest,
    AccountData,
    PositionData,
    TickData
)
from vnpy.trader.constant import (
    Exchange,
    OrderType,
    Direction,
    Interval
)
from vnpy_longport import LongPortGateway


def process_account_event(event: Event) -> None:
    """处理账户事件"""
    account: AccountData = event.data
    print(f"收到账户更新：{account}")


def process_position_event(event: Event) -> None:
    """处理持仓事件"""
    position: PositionData = event.data
    print(f"收到持仓更新：{position}")


def process_tick_event(event: Event) -> None:
    """处理行情事件"""
    tick: TickData = event.data
    print(f"收到行情更新：{tick}")


def process_log_event(event: Event) -> None:
    """处理日志事件"""
    log: str = event.data
    print(f"收到日志：{log}")


def main():
    """测试长桥接口"""
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 注册事件处理函数
    event_engine.register("eAccount", process_account_event)
    event_engine.register("ePosition", process_position_event)
    event_engine.register("eTick", process_tick_event)
    event_engine.register("eLog", process_log_event)
    
    # 创建主引擎（会自动启动事件引擎）
    main_engine = MainEngine(event_engine)
    
    # 添加长桥接口
    main_engine.add_gateway(LongPortGateway)
    
    # 连接长桥
    setting = {
        "app_key": "d31b1c4329a22f60273a85962920e81a",
        "app_secret": "65affcfb4d964b825388ccce3c881959272bb93a0a58dcb2ee20a4e0fec03b88",
        "access_token": "m_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJsb25nYnJpZGdlIiwic3ViIjoiYWNjZXNzX3Rva2VuIiwiZXhwIjoxNzUxMzU4OTEyLCJpYXQiOjE3NDM1ODI5MTMsImFrIjoiZDMxYjFjNDMyOWEyMmY2MDI3M2E4NTk2MjkyMGU4MWEiLCJhYWlkIjoyMDQ2ODM1MSwiYWMiOiJsYl9wYXBlcnRyYWRpbmciLCJtaWQiOjEwMTg2MDU4LCJzaWQiOiJ1TFlvdWUvZzRYRzdwUW9FSHJLbWNRPT0iLCJibCI6MywidWwiOjAsImlrIjoibGJfcGFwZXJ0cmFkaW5nXzIwNDY4MzUxIn0.vmnSMNB0vhrxvWyrGVu77bvgFwpYaAuw77NQquG2MCCCat_ykMtK5-hugxBRNB3sWjBbqlxWNagfmf1RzeMeZbPcnWamw3AWygaWwOfr30eUA5f2If12RMfjX2uKIiff4AUJyFD5x4FoyCg3dnXUqVV4fjNWygkHRdZeLdWGQAhGcKkNKVBZaVE0s1Mzwwj0sQuAzvz0cj73_KiQmp2T6mrFlpfE77w7BHrFsrDcMNfiBi1Uhn57qYRC0bbbXzXMFeh9f2PMrzaLocUfFCvSsuyOEpgCLu6gWiYxHCyMLM0EHPXP9SX6IFUKJVykgGuwamGpl1bvEQRe7aYeYK3T23Fk_umF1SbTSthW0WX7GAgJLyTnuLkeAWOiixcfikEJ2R2g2uzUqqj8jVX-ecmxhffKWMeDmEiONMVtDODaZSftnDDLHj8NpI4rNEkBTfGa7Vr6AsGw-REwL-LKL040YcKpdcMQUEZTsnwnRninfvwXQZTljd3x2JlUPGNwTIoIKfiob0uisVFz0goMuZMQDq9fWpsU9Ni-E-ApBT_QtCh288yX1yfQFvTbDO3Wtdov48lL3zXQnJ-h31aCA3EHEMTxc4F6mNV5Al37Xx5Th_xU8eKw6hTC3OPDtOUpdazenEW42eSmWNRM3RIN0oygFrqlLo87Uyj7CajIY3zntR8"
    }
    print("开始连接长桥...")
    main_engine.connect(setting, "LONGPORT")
    
    # 等待连接
    print("等待连接建立...")
    time.sleep(5)
    
    # 订阅行情
    print("开始订阅行情...")
    req = SubscribeRequest(
        symbol="700",  # 腾讯控股
        exchange=Exchange.SEHK
    )
    main_engine.subscribe(req, "LONGPORT")
    
    # 查询历史数据
    print("开始查询历史数据...")
    history_req = HistoryRequest(
        symbol="700",
        exchange=Exchange.SEHK,
        interval=Interval.DAILY,
        start=datetime.now() - timedelta(days=5),
        end=datetime.now()
    )
    # print(f"历史数据请求：{history_req}")
    bars = main_engine.query_history(history_req, "LONGPORT")
    # print(f"历史数据：{bars}")
    
    # 查询账户信息
    print("开始查询账户信息...")
    gateway = main_engine.get_gateway("LONGPORT")
    if gateway:
        gateway.query_account()
        time.sleep(1)  # 等待账户信息更新
        account = main_engine.get_account("LONGPORT")
        print(f"账户信息：{account}")
    else:
        print("找不到LONGPORT网关")
    
    # 查询持仓信息
    print("开始查询持仓信息...")
    if gateway:
        gateway.query_position()
        time.sleep(1)  # 等待持仓信息更新
        positions = main_engine.get_all_positions()
        print(f"持仓信息：{positions}")
    else:
        print("找不到LONGPORT网关")
    
    # 保持运行
    print("开始持续运行...")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main() 