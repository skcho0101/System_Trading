# -*- coding: utf-8 -*-
"""
Created on Sat Oct 30 22:57:02 2021

@author: skcho
"""

import logging
import queue
import threading
import time
import tkinter

import os
import datetime
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QObject
gv_msg = ''

def createfolder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def createfile(foldername, filename):
      now = datetime.datetime.now()
      nowtuple = now.timetuple()
      createfolder(foldername)
      foldername = foldername + str(nowtuple.tm_year) + '/'
      createfolder(foldername)
      foldername = foldername + str(nowtuple.tm_mon) + '/'
      createfolder(foldername)
      foldername = foldername + str(nowtuple.tm_mday) + '/'
      createfolder(foldername)
      logfile = foldername + filename + '.log'
      return logfile

#planTextEidt 에로그 쓰기
class Handler(QObject, logging.Handler):
    new_record = pyqtSignal(object)

    def __init__(self, parent):
        super().__init__(parent)
        super(logging.Handler).__init__()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.new_record.emit(msg) # <---- emit signal here

class Formatter(logging.Formatter):
    def formatException(self, ei):
        result = super(Formatter, self).formatException(ei)
        return result

    def format(self, record):
        s = super(Formatter, self).format(record)
        if record.exc_text:
            s = s.replace('\n', '')
        return s 
###############################################################################

#####################TKINTERD에 로그 쓰기
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.text_widget.after(100, self.poll_queue)  # Start polling message from the queue

    def close(self):
        self.queue.join()

    def emit(self, record):
        self.queue.put(record)

    def poll_queue(self):
        # Check every 100 ms if there is a new message in the queue to display
        while not self.queue.empty():
            msg = self.queue.get(block=False)
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tkinter.END, self.format(msg) + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tkinter.END)  # Autoscroll to the bottom
            self.queue.task_done()
        self.text_widget.after(100, self.poll_queue)


class LogWidget(tkinter.Frame):
    def __init__(self, logfile=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        tkinter.Button(self, text='Clear', command=self.clear).grid(row=0, column=0)

        self.text = tkinter.Text(self, wrap='none', borderwidth=0)
        text_vsb = tkinter.Scrollbar(self, orient='vertical', command=self.text.yview)
        text_hsb = tkinter.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=text_vsb.set, xscrollcommand=text_hsb.set, font='TkFixedFont')

        self.text.grid(row=1, column=0, sticky='nsew')
        text_vsb.grid(row=1, column=1, sticky='ns')
        text_hsb.grid(row=2, column=0, sticky='ew')

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.pack(side='top', fill='both', expand=True)

        # logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.text_handler = TextHandler(self.text)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.text_handler.setFormatter(formatter)
        #logger = logging.getLogger()
        #logger.addHandler(self.text_handler)
        #logger.setLevel(logging.INFO)
        
    def setlogger(self,logger1):
        logger1.addHandler(self.text_handler)
        logger1.setLevel(logging.INFO)
   
                
    def destroy(self):
        logging.getLogger().removeHandler(self.text_handler)
        print('destroy')

    def clear(self):
        self.text.configure(state='normal')
        self.text.delete('1.0', tkinter.END)
        self.text.configure(state='disabled')
############################################################################################
   
#################파일에 로그 쓰기    
def make_logger(filename):
            #
         foldername = './Log'
         logger = logging.getLogger(filename)
         logger.setLevel(logging.DEBUG)    
    
         # 핸들러 리셋
         for hdlr in logger.handlers[:]:  # remove all old handlers
             logger.removeHandler(hdlr)
    
         # 일자별 폴더 생성
         logfile = createfile(foldername, filename)
    
         # 핸들러 설정
         logfomatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
         logfilemaxbyte = 1024 * 1024 * 100 # 100MB
         logfilehandler = logging.handlers.RotatingFileHandler(logfile, maxBytes=logfilemaxbyte, backupCount=10)
         logstreamhandler = logging.StreamHandler()
         logfilehandler.setFormatter(logfomatter)
         logstreamhandler.setFormatter(logfomatter)
         logger.addHandler(logfilehandler)
         logger.addHandler(logstreamhandler) 
  
     
         return logger



log1 = make_logger('SendMsg')
log2 = make_logger('RecvMsg')



def AddLog(str,type):
    if type == 0:   #seq
        log1.info(str)
    elif type == 1: #comm
        log2.info(str)   


'''
def ShowLogUI(type):
    root.mainloop()

     if type == 0:
        root.mainloop()
        root.destroy()
        print('root1 destroy')
     elif type == 1:
        root1.mainloop()
        root1.destroy()  
        print('root2 destroy')
''''        '''
     


   

# =============================================================================
# 
# 
# def main():
#     root = tkinter.Tk()
#     LogWidget(master=root)
# 
#     def worker():
#        while True:
#             time.sleep(1)
#             #msg = f'Current time: {time.asctime()}'
#             logging.info(gb_msg)
# 
#     t1 = threading.Thread(target=worker, args=[])
#     t1.start()
# 
#     root.mainloop()
#  
#     t1.join()
# 
# =============================================================================

#if __name__ == "__main__":
 #   main()
