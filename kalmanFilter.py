#region imports
from AlgorithmImports import *
#endregion

import numpy as np
from math import floor

class KalmanFilter:
    def __init__(self):
        self.delta = 1e-4
        self.wt = self.delta / (1 - self.delta) * np.eye(2)
        self.vt = 1e-3
        self.theta = np.zeros(2)
        self.P = np.zeros((2, 2))
        self.R = None
        self.qty = 6000



    def update(self, price_one, price_two):
        # Create the observation matrix of the latest prices
        # of TLT and the intercept value (1.0)
        F = np.asarray([price_one, 1.0]).reshape((1, 2))
        y = price_two
        
        # The prior value of the states \theta_t is
        # distributed as a multivariate Gaussian with
        # mean a_t and variance-covariance R_t
        if self.R is not None:
            self.R = self.C + self.wt
        else:
            self.R = np.zeros((2, 2))
        
        # Calculate the Kalman Filter update
        # ----------------------------------
        # Calculate prediction of new observation
        # as well as forecast error of that prediction
        yhat = F.dot(self.theta)
        et = y - yhat
        
        # Q_t is the variance of the prediction of
        # observations and hence \sqrt{Q_t} is the
        # standard deviation of the predictions
        Qt = F.dot(self.R).dot(F.T) + self.vt
        sqrt_Qt = np.sqrt(Qt)
        
        # The posterior value of the states \theta_t is
        # distributed as a multivariate Gaussian with mean
        # m_t and variance-covariance C_t
        At = self.R.dot(F.T) / Qt
        self.theta = self.theta + At.flatten() * et
        self.C = self.R - At * F.dot(self.R)
        
        hedge_quantity = int(floor(self.qty*self.theta[0]))
        return et, sqrt_Qt, hedge_quantity



