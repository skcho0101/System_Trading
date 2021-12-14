# -*- coding: utf-8 -*-
"""
Created on Sat Oct 30 14:29:17 2021

@author: skcho
"""

from LogWidget import *
  
class LogCtrl:

    
  
    @staticmethod
    def AddLog(str,mode=0):      
        if mode == 0:
            #LogWidget.Sklogging('Sequence').info(str)               
           logging.info(str)       
        elif mode ==1:
            LogWidget('Comm').info(str) 
          

    
    