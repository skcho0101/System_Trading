from api.Kiwoom import *
from util.make_up_universe import *
from strategy.RSIStrategy import *
import sys

#git_test1





#kiwoom = Kiwoom()

''''''''''
kospi_code_list = kiwoom.get_code_list_by_market("0")
print(kospi_code_list)

for code in kospi_code_list:
    code_name = kiwoom.get_master_code_name(code)
    print(code,code_name)

df = kiwoom.get_price_data("336260")
print(df)
'''
#deposit = kiwoom.get_deposit()

#orders = kiwoom.get_order()  #주문 정보 얻어오기
#position = kiwoom.get_balance()
#print(position)

# fids = get_fid("체결시간")
# codes = '005930;007700;000660'
# kiwoom.set_real_reg("1000",codes,fids,"0")


app = QApplication(sys.argv)
rsi_strategy = RSIStrategy()
rsi_strategy.start()

app.exec_()

