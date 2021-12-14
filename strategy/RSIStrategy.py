from api.Kiwoom import *
from util.make_up_universe import *
from util.db_helper import *
from util.time_helper import *
from util.notifier import *
import math
import traceback


class RSIStrategy(QThread):
    def __init__(self):
        QThread.__init__(self)
        self.strategy_name = "RSIStrategy"
        self.kiwoom = Kiwoom()
        self.universe = {}  #유니버스 정보를 담을 딕셔너리
        self.deposit = 0  #예수금 계좌
        self.is_init_success = False  #초기화 함수 성공 여부 확인 변수
        self.init_strategy()


    def init_strategy(self):
        try:
            self.check_and_get_universe()
            self.check_and_get_price_data()

            self.kiwoom.get_order()     #주문정보 확인
            self.kiwoom.get_balance()   #잔고 확인
            self.deposit = self.kiwoom.get_deposit() #예수금 확인
            self.set_universe_real_time() #유니버스 실시간 체결 정보 등록
            self.is_init_success = True

        except Exception as e:
            print(traceback.format_exc())
            send_message(traceback.format_exc(), RSI_STRATEGY_MESSAGE_TOKEN)


    def check_and_get_universe(self):
        if not check_table_exist(self.strategy_name,'universe'):
            universe_list = get_universe()
            print(universe_list)

            universe = {}
            now = datetime.now().strftime("%Y%m%d")

            kospi_code_list = self.kiwoom.get_code_list_by_market("0")
            kosdaq_code_list = self.kiwoom.get_code_list_by_market("10")

            for code in kospi_code_list + kosdaq_code_list:
                code_name = self.kiwoom.get_master_code_name(code)  #종목 코드에서 종목명 얻어옴
                #얻어 온 종목명이 유니버스에 포함되어 있다면 딕셔너리에 추가
                if code_name in universe_list:
                    universe[code] = code_name

            #코드, 종목명, 생성 일자를 열로 가지는 dataframe 생성
            universe_df = pd.DataFrame({
                'code':universe.keys(),
                'code_name':universe.values(),
                'created_at':[now]*len(universe.keys())
            })

            insert_df_to_db(self.strategy_name,'universe',universe_df)   #universe라는 테이블 이름으로 DataFrame을 DB에 저장

        sql = "select * from universe"
        cur = execute_sql(self.strategy_name,sql)
        universe_list = cur.fetchall()
        for item in universe_list:
            idx, code, code_name, created_at = item
            self.universe[code] = {
                'code_name':code_name
            }

        print(self.universe)
    #일봉 데이터가 있는지 확인하고 없다면 생성하는 함수
    def check_and_get_price_data(self):
        for idx, code in enumerate(self.universe.keys()):
            print("({}/{}) {}".format(idx+1,len(self.universe),code))

            if check_transaction_closed() and not check_table_exist(self.strategy_name,code):
            #if not check_table_exist(self.strategy_name, code):
                price_df = self.kiwoom.get_price_data(code)
                insert_df_to_db(self.strategy_name, code, price_df)
            else:
                if check_transaction_closed():
                    sql = "select max(`{}`) from `{}`".format('index', code)
                    cur = execute_sql(self.strategy_name, sql)

                    last_date = cur.fetchone()

                    now = datetime.now().strftime("%Y%m%d")

                    if last_date[0] != now:
                        price_df = self.kiwoom.get_price_data(code)

                        insert_df_to_db(self.strategy_name,code,price_df)
                else:
                    sql = "select * from '{}'".format(code)
                    cur = execute_sql(self.strategy_name,sql)
                    cols=[column[0] for column in cur.description]

                    price_df = pd.DataFrame.from_records(data = cur.fetchall(), columns = cols)
                    price_df = price_df.set_index('index')
                    self.universe[code]['price_df'] = price_df

#유니버스의 실시간 체결정보 수신을 등록하는 함수
    def set_universe_real_time(self):
        fids = get_fid("체결시간")
        #self.kiwoom.set_real_req("1000","",get_fid("장운영구분"),"0")

        codes = self.universe.keys() #universe 딕셔너리의 키값들은 종목 코드들을 의미
        codes = ";".join(map(str,codes))

        self.kiwoom.set_real_reg("9999", codes, fids, "0")

    def check_sell_signal(self,code):
        universe_item = self.universe[code]
        print(universe_item)
        print(universe_item.keys())

        # (1)현재 체결정보가 존재하지 않는지 확인
        if code not in self.kiwoom.universe_realtime_transaction_info.keys():
            # 체결 정보가 없으면 더 이상 진행하지 않고 함수 종료
            print("매도대상 확인 과정에서 아직 체결정보가 없습니다.")
            return

        # (2)실시간 체결 정보가 존재하면 현시점의 시가 / 고가 / 저가 / 현재가 / 누적 거래량이 저장되어 있음
        open = self.kiwoom.universe_realtime_transaction_info[code]['시가']
        high = self.kiwoom.universe_realtime_transaction_info[code]['고가']
        low = self.kiwoom.universe_realtime_transaction_info[code]['저가']
        close = self.kiwoom.universe_realtime_transaction_info[code]['현재가']
        volume = self.kiwoom.universe_realtime_transaction_info[code]['누적거래량']

        # 오늘 가격 데이터를 과거 가격 데이터(DataFrame)의 행으로 추가하기 위해 리스트로 만듦
        today_price_data = [open, high, low, close, volume]

        df = universe_item['price_df'].copy()

        # 과거 가격 데이터에 금일 날짜로 데이터 추가
        df.loc[datetime.now().strftime('%Y%m%d')] = today_price_data

        # RSI(N) 계산
        period = 2  # 기준일 설정
        date_index = df.index.astype('str')
        # df.diff를 통해 (기준일 종가 - 기준일 전일 종가)를 계산하여 0보다 크면 증가분을 넣고, 감소했으면 0을 넣어줌
        U = np.where(df['close'].diff(1) > 0, df['close'].diff(1), 0)
        # df.diff를 통해 (기준일 종가 - 기준일 전일 종가)를 계산하여 0보다 작으면 감소분을 넣고, 증가했으면 0을 넣어줌
        D = np.where(df['close'].diff(1) < 0, df['close'].diff(1) * (-1), 0)
        AU = pd.DataFrame(U, index=date_index).rolling(window=period).mean()  # AU, period=2일 동안의 U의 평균
        AD = pd.DataFrame(D, index=date_index).rolling(window=period).mean()  # AD, period=2일 동안의 D의 평균
        RSI = AU / (AD + AU) * 100  # 0부터 1로 표현되는 RSI에 100을 곱함
        df['RSI(2)'] = RSI

        # 보유 종목의 매입가격 조회
        purchase_price = self.kiwoom.balance[code]['매입가']
        # 금일의 RSI(2) 구하기
        rsi = df[-1:]['RSI(2)'].values[0]

        # 매도 조건 두 가지를 모두 만족하면 True
        if rsi > 80 and close > purchase_price:
            return True
        else:
            return False
    #매도 주문 접수 함수
    def order_sell(self,code):
        quantity = self.kiwoom.balance[code]['보유수량']
        ask = self.kiwoom.universe_realtime_transaction_info[code]['(최우선)매도호가']
        order_result = self.kiwoom.send_order('send_sell_order','1001',2 , code, quantity, ask,'00')
        # LINE 메시지를 보내는 부분
        message = "[{}]sell order is done! quantity:{}, ask:{}, order_result:{}".format(code, quantity, ask,
                                                                                        order_result)
        send_message(message, RSI_STRATEGY_MESSAGE_TOKEN)

    def check_buy_signal_and_order(self, code):
        """매수 대상인지 확인하고 주문을 접수하는 함수"""

        # 매수 가능 시간 확인
        if check_adjacent_transaction_closed():
            print("check_adjacent_transaction_closed")
            return False

        universe_item = self.universe[code]

        # (1)현재 체결정보가 존재하지 않는지 확인
        if code not in self.kiwoom.universe_realtime_transaction_info.keys():
            # 존재하지 않다면 더이상 진행하지 않고 함수 종료
            print("매수대상 확인 과정에서 아직 체결정보가 없습니다.")
            return

        # (2)실시간 체결 정보가 존재하면 현 시점의 시가 / 고가 / 저가 / 현재가 / 누적 거래량이 저장되어 있음
        open = self.kiwoom.universe_realtime_transaction_info[code]['시가']
        high = self.kiwoom.universe_realtime_transaction_info[code]['고가']
        low = self.kiwoom.universe_realtime_transaction_info[code]['저가']
        close = self.kiwoom.universe_realtime_transaction_info[code]['현재가']
        volume = self.kiwoom.universe_realtime_transaction_info[code]['누적거래량']

        # 오늘 가격 데이터를 과거 가격 데이터(DataFrame)의 행으로 추가하기 위해 리스트로 만듦
        today_price_data = [open, high, low, close, volume]

        df = universe_item['price_df'].copy()

        # 과거 가격 데이터에 금일 날짜로 데이터 추가
        df.loc[datetime.now().strftime('%Y%m%d')] = today_price_data

        # RSI(N) 계산
        period = 2  # 기준일 설정
        date_index = df.index.astype('str')
        # df.diff를 통해 (기준일 종가 - 기준일 전일 종가)를 계산하여 0보다 크면 증가분을 넣고, 감소했으면 0을 넣어줌
        U = np.where(df['close'].diff(1) > 0, df['close'].diff(1), 0)
        # df.diff를 통해 (기준일 종가 - 기준일 전일 종가)를 계산하여 0보다 작으면 감소분을 넣고, 증가했으면 0을 넣어줌
        D = np.where(df['close'].diff(1) < 0, df['close'].diff(1) * (-1), 0)
        AU = pd.DataFrame(U, index=date_index).rolling(window=period).mean()  # AU, period=2일 동안의 U의 평균
        AD = pd.DataFrame(D, index=date_index).rolling(window=period).mean()  # AD, period=2일 동안의 D의 평균
        RSI = AU / (AD + AU) * 100  # 0부터 1로 표현되는 RSI에 100을 곱함
        df['RSI(2)'] = RSI

        # 종가(close)를 기준으로 이동 평균 구하기
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()

        rsi = df[-1:]['RSI(2)'].values[0]
        ma20 = df[-1:]['ma20'].values[0]
        ma60 = df[-1:]['ma60'].values[0]

        # 2 거래일 전 날짜(index)를 구함
        idx = df.index.get_loc(datetime.now().strftime('%Y%m%d')) - 2

        # 위 index로부터 2 거래일 전 종가를 얻어옴
        close_2days_ago = df.iloc[idx]['close']

        # 2 거래일 전 종가와 현재가를 비교함
        price_diff = (close - close_2days_ago) / close_2days_ago * 100

        # (3)매수 신호 확인(조건에 부합하면 주문 접수)
        if ma20 > ma60 and rsi < 5 and price_diff < -2:
            # (4)이미 보유한 종목, 매수 주문 접수한 종목의 합이 보유 가능 최대치(10개)라면 더 이상 매수 불가하므로 종료
            if (self.get_balance_count() + self.get_buy_order_count()) >= 10:
                return

            # (5)주문에 사용할 금액 계산(10은 최대 보유 종목 수로써 consts.py에 상수로 만들어 관리하는 것도 좋음)
            budget = self.deposit / (10 - (self.get_balance_count() + self.get_buy_order_count()))

            # 최우선 매도호가 확인
            bid = self.kiwoom.universe_realtime_transaction_info[code]['(최우선)매수호가']

            # (6)주문 수량 계산(소수점은 제거하기 위해 버림)
            quantity = math.floor(budget / bid)

            # (7)주문 주식 수량이 1 미만이라면 매수 불가하므로 체크
            if quantity < 1:
                return

            # (8)현재 예수금에서 수수료를 곱한 실제 투입금액(주문 수량 * 주문 가격)을 제외해서 계산
            amount = quantity * bid
            self.deposit = math.floor(self.deposit - amount * 1.00015)

            # (8)예수금이 0보다 작아질 정도로 주문할 수는 없으므로 체크
            if self.deposit < 0:
                return

            # (9)계산을 바탕으로 지정가 매수 주문 접수
            order_result = self.kiwoom.send_order('send_buy_order', '1001', 1, code, quantity, bid, '00')

            # _on_chejan_slot가 늦게 동작할 수도 있기 때문에 미리 약간의 정보를 넣어둠
            self.kiwoom.order[code] = {'주문구분': '매수', '미체결수량': quantity}

            # LINE 메시지를 보내는 부분
            message = "[{}]buy order is done! quantity:{}, bid:{}, order_result:{}, deposit:{}, get_balance_count:{}, get_buy_order_count:{}, balance_len:{}".format(
                code, quantity, bid, order_result, self.deposit, self.get_balance_count(), self.get_buy_order_count(),
                len(self.kiwoom.balance))
            send_message(message, RSI_STRATEGY_MESSAGE_TOKEN)
            # LINE 메시지를 보내는 부분
            message = "[{}]buy order is done! quantity:{}, bid:{}, order_result:{}, deposit:{}, get_balance_count:{}, get_buy_order_count:{}, balance_len:{}".format(
                code, quantity, bid, order_result, self.deposit, self.get_balance_count(), self.get_buy_order_count(),
                len(self.kiwoom.balance))
            send_message(message, RSI_STRATEGY_MESSAGE_TOKEN)
        # 매수신호가 없다면 종료
        else:
            print("매수 조건이 없습니다.")
            return

    def get_balance_count(self):
        """매도 주문이 접수되지 않은 보유 종목 수를 계산하는 함수"""
        balance_count = len(self.kiwoom.balance)
        # kiwoom balance에 존재하는 종목이 매도 주문 접수되었다면 보유 종목에서 제외시킴
        for code in self.kiwoom.order.keys():
            if code in self.kiwoom.balance and self.kiwoom.order[code]['주문구분'] == "매도" and self.kiwoom.order[code]['미체결수량'] == 0:
                balance_count = balance_count - 1
        return balance_count

    def get_buy_order_count(self):
        """매수 주문 종목 수를 계산하는 함수"""
        buy_order_count = 0
        # 아직 체결이 완료되지 않은 매수 주문
        for code in self.kiwoom.order.keys():
            if code not in self.kiwoom.balance and self.kiwoom.order[code]['주문구분'] == "매수":
                buy_order_count = buy_order_count + 1
        return buy_order_count




    def run(self):
        print("RSIStrategy Start")
        while self.is_init_success:
            try:
                if not check_transaction_open(): # 장 중인지 확인
                    print("장시간이 아니므로 5분간 대기합니다.")
                    time.sleep(5* 60)
                    continue

                for inx, code in enumerate(self.universe.keys()):
                    print('[{}/{}_{}]'.format(inx+1, len(self.universe), self.universe[code]['code_name']))
                    time.sleep(0.5)

                    if code in self.kiwoom.order.keys():
                        print('접수 주문',self.kiwoom.order[code])
                        if self.kiwoom.order[code]['미체결수량'] > 0:
                            pass

                    elif code in self.kiwoom.balance.keys():  #보유 종목인지 확인
                        print('보유 종목',self.kiwoom.balance[code])

                        if self.check_sell_signal(code):  #매도 대상 확인
                            self.order_sell(code)

                    else:
                        self.check_buy_signal_and_order(code)   #접수한 종목 및 보유 종목이 아니라면 매수 대상인지 확인 후 주문 접수수



            except Exceptio as e:
                    print(traceback.format_exc())
                    send_message(traceback.format_exc(), RSI_STRATEGY_MESSAGE_TOKEN)




