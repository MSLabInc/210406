import serial, sys, queue
from collections import deque
import re
import time
from threading import Event, Thread
import RPi.GPIO as GPIO
# import setting

"""
    USBから温度取得用スレッド
"""

class TempReader(Thread):
    def __init__(self, str_port, rate, tc_index, q_maxlen, save_file=None):
        Thread.__init__(self)

        # 温度用のキュー
        """
        SSRごとに queue をつくる
        （temperature のlistの場所としての index ）
        """
        self.tc_index = tc_index
        self.q_maxlen = q_maxlen
        self.tc_queue_dict = {}
        self.tc_now = {}
        for idx in tc_index:
            self.tc_queue_dict[idx] = deque(maxlen=q_maxlen)
            self.tc_now[idx] = None

        # 外部からスレッド停止用
        self.running = True

        # シリアルポート設定
        self.str_port = str_port
        self.rate = rate

        self.ser = serial.Serial(str_port, rate, timeout = 0) #20200627 115200->19200
        self.ser.send_break()
        self.ser.reset_input_buffer
        self.ser.reset_input_buffer
        self.ser.reset_input_buffer
        self.ser.reset_input_buffer
        line_byte = self.ser.readline()  #一回、読み飛ばしをかける
        # line_byte = line_byte.decode(encoding='utf-8')
        # temperatures = line_byte.split(',')
        # print(f"[Debug] line_s = {temperatures}")
        # self.tc_queue_dict.put(temperatures[2])
        # print(f"{self.str_port}, {tc_queue_dict.qsize()}")
        #一回バッファークリアしないといけない？？？
        self.ser.reset_input_buffer
        
        # ログファイル
        self.fw = open(save_file, "w+")

        time.sleep(0.2)

    def run(self):

        Debug0=False #debug print flag
        Debug1=False
        Debug2=False
        Debug3=False
        
        q=[] # {210118} Temperature history, list during some period
        
        event = Event()
        event.set()

        time.sleep(3)
        while self.running:
            buff_waiting = self.ser.in_waiting

            # print(f"buff_waiting: {buff_waiting}")
            # バッファーにデータ有
            if buff_waiting > 0:
                line_byte = self.ser.readline()
                line_byte = line_byte.decode(encoding='utf-8')
                temperatures=line_byte.split(',')
                self.fw.write(",".join(temperatures))   # ファイルへ保存
                if Debug0: print("Debug0,in temp.reader",f"line_s = {temperatures}")

                # キューに温度をいれる（SSR制御で使用）
                if Debug2:
                      print("Debug2 in temp.reader; fetch temp each of 0.1 sec,",f"{self.str_port}: {temperatures}")
                      print("#############",self.tc_index,"#####################")
                for idx in self.tc_index:
#                for idx in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:   <==not OK
#                for idx in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:    <==OK
                    if idx == 0:
                        if Debug1: 
                           print("Debug1 in debug_temp_reader   idx==0",temperatures[idx]) #this is tc-logger number 
                           # num0=temperatures[0].strip().decode('utf-8') #{210117} chibaf
                           #num0=int(temperatures[idx]) #{210117} chibaf
                           #print("num0=",num0)
                        #temperatures[idx]=float(chr(temperatures[idx]))
                        self.tc_queue_dict[0].append(temperatures[0])  #いちおう、そのまま、transferする
                        self.tc_now[0] = temperatures[0]   
                        
                    elif idx == 1:
                        a=temperatures[1].find(':')
                        b=temperatures[1].rfind(':')
                        hour_float=float(temperatures[1][:a])
                        min_float=float(temperatures[1][a+1:b])
                        second_float=float(temperatures[1][temperatures[1].rfind(':')+1:])
                        seconds_at_Tc_reader=3600*hour_float+60*min_float+second_float
                        temperatures[1]=seconds_at_Tc_reader
                        self.tc_queue_dict[1].append(float(temperatures[1]))      
                        self.tc_now[1] = float(temperatures[1])   
                        if Debug2:                          
                            print("Debug2 in debug_temp_reader   idx==1 {210104}  ",
                            "time=",temperatures[1],"     ",
                            "hour=(float)",hour_float,
                            "min(float)=",min_float,
                            "second(float)=",second_float,
                            "seconds_at_Tc_reader",seconds_at_Tc_reader
                            )
                        #{210116}
                        #このtc_queue_dictの使い方がよくわからない。
                        #self.tc_queue_dict[idx].append(seconds_at_Tc_reader) #{210116}
                    else:
                        self.tc_queue_dict[idx].append(float(temperatures[idx]))      
                        self.tc_now[idx] = float(temperatures[idx])   
                    if Debug1: print("Debug1 in debug_temp_reader  ","idx",idx,"temperatures[idx]",temperatures[idx])
                
                if Debug3: 
                   print("Debug3 in debug_temp_reader,  self.tc_now=",self.tc_now)
                   print("Debug3 in debug_temp_reader, seconds_at_Tc_reader",seconds_at_Tc_reader)
                   
                                                
                """
                先頭への要素の削除をO(1)で行う型として標準ライブラリcollectionsモジュールにdeque型が用意されている。
                例えばデータをキュー（queue, FIFO）として扱いたい場合はdequeを使うほうが効率的。
                """

                """
                時間幅をいちおう計算して（0.1秒づつとっているはずだが）、dT/dt を計算できるようにしておく。
                """
                
                #print(f"{self.str_port}, {self.tc_queue_dict.qsize()}")
                """
                T_measは、Tc-1なので、これをPIDの計測値としてPID制御をする。
                tempertures[2]
                """
                # q.put(line_byte)
                # if False :
                # print(buff_waiting, q.qsize(), line_byte)
            event.wait()
        # 終了処理
        self.ser.close()
        self.fw.close()
        print(f"exit usb: {self.str_port}")
    
    def close(self):
        """
        外部からスレッド停止用メソッド
        """
        print(f"close usb: {self.str_port}")
        self.running = False

    def get_tc_now(self, idx):

        return self.tc_now[idx]

    def get_tc_average(self, idx):

        """
        {210116}
        ここで、履歴データを処理して、
        SSRへの指示パラメータを用意する、
        こともできる
        """
        
        total = 0
        for tc_hist in self.tc_queue_dict[idx]:
            total += tc_hist

        return total / self.q_maxlen
        
        

    def comment_210104(self):
        s1="""
        K{210104}
        コメント、self.tc_now = temperatures[idx]  で ssrに情報を送り込んでいる。
        temperatures[idex]の中身は（例えば）以下のようになっている
                    idx= 0   temperatures[idex]=  02
                    idx= 1   temperatures[idex]=  188:56:33.2　これが時刻
                    idx= 2   temperatures[idex]=  11.0625
                    idx= 3   temperatures[idex]=  10.6875
                    idx= 4   temperatures[idex]=  10.8750
                    idx= 5   temperatures[idex]=  11.0625
                    idx= 6   temperatures[idex]=  11.3125
                    idx= 7   temperatures[idex]=  11.3125
                    idx= 8   temperatures[idex]=  11.3125
                    idx= 9   temperatures[idex]=  11.1250
        """
        print(s1)



        
