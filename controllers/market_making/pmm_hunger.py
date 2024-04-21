import time
from decimal import Decimal
from typing import List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import PriceType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.executor_actions import ExecutorAction, StopExecutorAction


class PMMHungerConfig(MarketMakingControllerConfigBase):
    controller_name = "pmm_hunger"
    candles_config: List[CandlesConfig] = Field(default=[], client_data=ClientFieldData(prompt_on_new=False))
    candles_connector: str = Field(
        default=None,
        client_data=ClientFieldData(
            prompt_on_new=False,
            prompt=lambda mi: "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",
        ),
    )
    candles_trading_pair: str = Field(
        default=None,
        client_data=ClientFieldData(
            prompt_on_new=False,
            prompt=lambda mi: "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",
        ),
    )
    interval: str = Field(
        default="1m",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            prompt_on_new=False,
        ),
    )
    top_order_refresh_time: Optional[float] = Field(
        default=None,
        client_data=ClientFieldData(
            is_updatable=True,
            prompt_on_new=False,
        ),
    )
    natr_length: int = Field(
        default=14,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the NATR length: ",
            prompt_on_new=False,
        ),
    )


class PMMHungerController(MarketMakingControllerBase):
    def __init__(self, config: PMMHungerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.max_records = config.natr_length * 2
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [
                CandlesConfig(
                    connector=config.candles_connector,
                    trading_pair=config.candles_trading_pair,
                    interval=config.interval,
                    max_records=self.max_records,
                )
            ]
        self.config = config

    def first_level_refresh_condition(self, executor):
        if self.config.top_order_refresh_time is not None:
            if self.get_level_from_level_id(executor.custom_info["level_id"]) == 1:
                return time.time() - executor.timestamp > self.config.top_order_refresh_time
        return False

    def order_level_refresh_condition(self, executor):
        return time.time() - executor.timestamp > self.config.executor_refresh_time

    def executors_to_refresh(self) -> List[ExecutorAction]:
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: not x.is_trading
            and x.is_active
            and (self.order_level_refresh_condition(x) or self.first_level_refresh_condition(x)),
        )
        return [
            StopExecutorAction(controller_id=self.config.id, executor_id=executor.id)
            for executor in executors_to_refresh
        ]

    def executors_to_early_stop(self) -> List[ExecutorAction]:
        return []

    async def update_processed_data(self):
        candles = self.market_data_provider.get_candles_df(
            connector_name=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.max_records,
        )
        natr = ta.natr(candles["high"], candles["low"], candles["close"], length=self.config.natr_length) / 100
        reference_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice
        )
        spread_multiplier = Decimal(natr.iloc[-1])
        self.processed_data = {"reference_price": reference_price, "spread_multiplier": spread_multiplier}

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=time.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )
