from AlgorithmImports import *
import numpy as np
from math import floor
import matplotlib.pyplot as plt
from kalmanFilter import KalmanFilter
from datetime import datetime

class PairsTradingAlgorithm(QCAlgorithm):

    def Initialize(self):
        # Define the pairs
        # pairs = [ ('KLAC', 'AMAT'), ('FRT', 'REG') ]
        pairs = [('KLAC', 'AMAT')]  
        # intervals = [3, 4]
        intervals = [3]
        
        # Set start and end date for backtest data
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 5, 4)
        
        # Set spending limit in cash
        self.SetCash(1000000)
        
        self.SetBrokerageModel(AlphaStreamsBrokerageModel())

        self.equities = []
        self.symbols = []
        self.invested = {}  # Dictionary to track invested status for each pair
        for pair in pairs:
            equity1 = self.AddEquity(pair[0], Resolution.Minute)
            equity2 = self.AddEquity(pair[1], Resolution.Minute)
            self.equities.extend([equity1, equity2])
            self.symbols.extend([equity1.Symbol, equity2.Symbol])

            # Set margin leverage to 1x so that we can only use cash we've set 
            for equity in [equity1, equity2]:
                equity.SetLeverage(1)

            # Initialize invested status for each pair as None
            self.invested[pair] = None

        # initialize Kalman Filter objects
        self.kf = KalmanFilter()

        for x in range(5, 366, 1):
            interval_count = 0
            for pair in pairs:
                if x % intervals[interval_count] == (5 % intervals[interval_count]):
                    self.Schedule.On(
                        self.DateRules.EveryDay(pair[0]),
                        self.TimeRules.BeforeMarketClose(pair[0], x),
                        self.UpdateAndTrade
                    )
                interval_count += 1
        
    def UpdateAndTrade(self):

        sensitivity_val_open_list = [2]
        sensitivity_val_close_list = [2]
        for pair_index in range(len(self.equities) // 2):
            equity1 = self.equities[pair_index * 2]
            equity2 = self.equities[pair_index * 2 + 1]
            symbol1 = self.symbols[pair_index * 2]
            symbol2 = self.symbols[pair_index * 2 + 1]

            if self.CurrentSlice is None:
                return

            stock1 = self.CurrentSlice[symbol1].Close
            stock2 = self.CurrentSlice[symbol2].Close
            holdings = self.Portfolio[symbol1]

            price1 = self.Portfolio[symbol1].AveragePrice
            price2 = self.Portfolio[symbol2].AveragePrice

            total_spread = abs(price1 - price2)
            current_spread = abs(stock1 - stock2)

            pair = (symbol1, symbol2)
            if pair not in self.invested:
                self.invested[pair] = None

            forecast_error, prediction_std_dev, hedge_quantity = self.kf.update(stock1, stock2)

            # Check if we are not invested
            if not holdings.Invested:
                # Enter long position on spread
                if forecast_error < ((sensitivity_val_open_list[pair_index] - 2) * prediction_std_dev):
                    insights = Insight.Group([
                        Insight(symbol1, timedelta(1), InsightType.Price, InsightDirection.Down),
                        Insight(symbol2, timedelta(1), InsightType.Price, InsightDirection.Up)
                    ])
                    self.EmitInsights(insights)
                    self.MarketOrder(symbol2, self.kf.qty)
                    self.MarketOrder(symbol1, -hedge_quantity)
                    self.invested[pair] = "long"
                    self.initial_spread = current_spread
                    self.initial_port_value = self.Portfolio.TotalPortfolioValue

                # Enter short position on spread
                elif forecast_error > (sensitivity_val_open_list[pair_index] * prediction_std_dev):
                    insights = Insight.Group([
                        Insight(symbol1, timedelta(1), InsightType.Price, InsightDirection.Up),
                        Insight(symbol2, timedelta(1), InsightType.Price, InsightDirection.Down)
                    ])
                    self.EmitInsights(insights)
                    self.MarketOrder(symbol2, -self.kf.qty)
                    self.MarketOrder(symbol1, hedge_quantity)
                    self.invested[pair] = "short"
                    self.initial_spread = current_spread
                    self.initial_port_value = self.Portfolio.TotalPortfolioValue

            # Check if we are invested
            if holdings.Invested:

                # 10% stop loss
                trailing_stop = 0.05
                profit_cap = 0.05

                # If long on spread
                if self.invested[pair] == "long":
                    
                    # boolean representing whether spread is "below" stop loss
                    # cut_losses = (current_spread < ((1 - trailing_stop) * self.initial_spread))
                    cut_losses = (self.Portfolio.TotalPortfolioValue < (1 - trailing_stop) * self.initial_port_value)

                    # old code
                    # if forecast_error >= -prediction_std_dev or current_spread < sensitivity_val_close_list[pair_index] * total_spread:

                    # Liquidate if current spread is below trailing stop or if forecast error is greater than or equal to -1 * predicted standard deviation
                    # if cut_losses or forecast_error >= -prediction_std_dev:

                    # cap_profits = (current_spread > (1 + profit_cap) * self.initial_spread)
                    cap_profits = (self.Portfolio.TotalPortfolioValue > (1 + profit_cap) * self.initial_port_value)

                    if cut_losses or cap_profits:
                        insights = Insight.Group([
                            Insight(symbol1, timedelta(1), InsightType.Price, InsightDirection.Flat),
                            Insight(symbol2, timedelta(1), InsightType.Price, InsightDirection.Flat)
                        ])
                        self.EmitInsights(insights)
                        self.Liquidate()
                        self.invested[pair] = None
                    
                    # Update the trailing stop if position is in profit (spread is increasing on long position)
                    if self.invested[pair] == None:
                        self.initial_spread = None
                    else:
                        self.initial_spread = max(self.initial_spread, current_spread)

                    self.initial_port_value = max(self.initial_port_value, self.Portfolio.TotalPortfolioValue)


                elif self.invested[pair] == "short":

                    # boolean representing whether spread is "below" stop loss (up 10% when in short position)
                    # cut_losses = (current_spread > ((1 + trailing_stop) * self.initial_spread))
                    cut_losses = (self.Portfolio.TotalPortfolioValue < (1 - trailing_stop) * self.initial_port_value)


                    # cap_profits = (current_spread < (1 - profit_cap) * self.initial_spread)
                    cap_profits = (self.Portfolio.TotalPortfolioValue > (1 + profit_cap) * self.initial_port_value)


                    # old code
                    # if forecast_error <= prediction_std_dev or current_spread > (2 - sensitivity_val_close_list[pair_index]) * total_spread:
                    
                    # Liquidate if current spread is below trailing stop or if forecast error is less than or equal to predicted standard deviation
                    # if cut_losses or forecast_error <= prediction_std_dev:
                    if cut_losses or cap_profits:
                        insights = Insight.Group([
                            Insight(symbol1, timedelta(1), InsightType.Price, InsightDirection.Flat),
                            Insight(symbol2, timedelta(1), InsightType.Price, InsightDirection.Flat)
                        ])
                        self.EmitInsights(insights)
                        self.Liquidate()
                        self.invested[pair] = None
                    
                    # Update the trailing stop if position is in profit (spread is decreasing on short position)
                    if self.invested[pair] == None:
                        self.initial_spread = None
                    else:
                        self.initial_spread = min(self.initial_spread, current_spread)

                    self.initial_port_value = max(self.initial_port_value, self.Portfolio.TotalPortfolioValue)





    