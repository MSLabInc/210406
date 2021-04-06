import sys, queue
import os
import re
import time

from threading import Thread
import RPi.GPIO as GPIO

"""
    SSR制御クラス

    設定温度：target_temp
    出力ピン：pin_num
    温度取得キュー：tc_readers_dict

"""
#target temperature ==> look at main.py, set_target_temp
room_temp= 15.0       #degree_C temperature
ki = 0.06  #0.001 for I-PD {210124A}
kp = 0.2  #0.0   for I-PD {200201}
kd = 0.1
pwm_total_time = 1.0  #It is very fast time-constant at NiCr wire heating 
MAX_PWM_WIDTH  = pwm_total_time
pwm_width_s_max = 0.95

Debug1=False
Debug2=False
Debug3=False
Debug4=False
Debug5=False
Debug6=True


"""
プログラムの構造
SsrDriver
  run(self)
     ==> self.get_pwm_width
     ==> self.set_pwm_width(pwm_width_s)
  get_pwm_width
    ==provide==> pwm_width_s
  set_pwm_width
    ==provide==> on_time, off_time
  set_target_temp
      (only) setting self.target_temp
  set_kp(self, kp) (いまは使っていない)
      (only) setting self.kp
  close(self)
"""




class SsrDriver(Thread):
    def __init__(self, target_pin, tc_readers_dict, target_temp=20): #target_temp=20 for default
        Thread.__init__(self)
        self.pin_num = target_pin["pin_num"]  # config.jsonでの SSR pin番号
        print(f"init SSR PIN({self.pin_num})")

        # 設定
        self.tc_index = target_pin["tc_index"]   # config.jsonでのSSRと組になっている熱電対の番号
        self.target_temp = target_temp
        self.ki = ki
        self.kp = kp
        self.kd = kd
        
        # contro; (I-PD, PID, etc)
        
                
        """
        {210116}
        このSsrDriverクラスのthreadは、main.pyで呼ばれて立ち上がる。
        main.py でSSR PIN({self.pin_num})　ごと別々のスレッドが立ち上がっている（確認要）。
        """
        """
        Kメモ{210103}
        ここ（def __init__ ）はあくまで、デフォルトのパラメータを決めていると言う位置づけで
        本当に制限をやっているのは、あるいはやるべきなのは、現場に1番近いところ。
        したがって、デフォルトのパラメータを、現場のプログラムに渡してあげると言う立ち位置になる。
        現場が無茶をやっても、ここで安全性を見てあげると言うような立場なのかもしれない。
        （試行錯誤でプログラムの構造を考えてみる。）
        """
        self.tc_readers_dict = tc_readers_dict

        self.running = True     # 外部からスレッドを止める用フラグ

        self.d_temp = None      # 温度差（将来PID制御用）  

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_num, GPIO.OUT)
        time.sleep(0.1)
        GPIO.output(self.pin_num, False)
        time.sleep(0.1)


    def run(self):

        time.sleep(0.2)
        print(f"start SSR PIN({self.pin_num})")  
        
        q=[] #{210119}
        max_q0 = None
        max_q49 = None  

        while self.running:

            try:
                """
                このプログラム1が1番、コントロールの現場に近いところで、本来あらゆる温度の情報とSSRの操作ができる
                作業フィールドになっているべき。今そうなっているかどうか、よくわからないけど。。。。。
                self.tc_readers_dict[input_port[0]].get_tc_now(input_port[1])　
                """
                list_tc_temp = []  
                # キューから温度を取得
                """
                K210104, ジェイソンの使い方、ジェイソンからデータとってくるところをきれいにわかるようにしないといけない
                （変数の説明）：
                 input_port= config.json の終端 
                            ['/dev/ttyUSB0', 2]　＝［Tc収録機のUARTの番号、「熱電対Tcの番号（文字列の位置）」］
                            input_port[1]は「熱電対Tcの番号」
                 get_tc_now = temperatures[idx] 最新値、吉澤さんのTc収録機から読み込んだcsv形式をばらしたもの
                 tc_readers_dict
                            この名前でスレッド（TempReaderを呼び出してTc収録機のデー打を受け取る）を立ち上げたもの。
                """
                
                if Debug1: print("debug_1 in ssr, self.tc_index=",self.tc_index)
                for input_port in self.tc_index:
                    if self.tc_readers_dict[input_port[0]].get_tc_now(input_port[1]) is not None:
                        list_tc_temp.append(
                          self.tc_readers_dict[input_port[0]].get_tc_now(input_port[1])
                          ) 
                # （config.jsonで書いてあるグループ化してある熱電対の）温度の最大値とか平均
                # ここで Group化を図っている
                if Debug1: print("debug_1 in ssr, list_tc_temp",list_tc_temp)
                
                
                """
                {210119}
                50 => 5sec　の間、 
                温度データをリストにして保管する   
                温度差をとって、それを5秒で割れば5秒で終われば、温度の上昇率が上がる。
                5秒の数値は後で本当は本当のデルタティーを使いたいんだけどちょっと後にする。作業はちょっと後にする。             
                """
                
                qq=list_tc_temp
                dtemp50dv_max=0 #initial setup
                if Debug3:
                  print("debug_3 in ssr, list_tc_temp, set q= append",list_tc_temp,"{210118}\n",qq,"{210118}\n")
                q.append(qq)
                qq=[]
                if Debug5:
                  print("q0=",q,"\n")
                if len(q)>50: 
                  q.pop(0)
                  if len(q[0]) > 0:
                    print("max(q[0], max(q[49]), max(q[49])-max(q[0]),  {210124}")
                    max_q0=max(q[0])
                    print(max(q[0]),"    {210124B}")
                    max_q49=max(q[49])
                    print(max(q[49]))
                    print(max(q[49])-max(q[0]))
                    dtemp50dv_max=(max(q[49])-max(q[0]))/(5.0) #divide by 5 seconds
                    if Debug3:
                      print("debug_3 in ssr, d(temp)/dt=",dtemp50dv_max,"{210119}")
                if Debug5: 
                  print("q0=",q,"\n")
                  print("\n")

                
                tc_temp_max = 0
                if len(list_tc_temp) > 0:
                    #tc_temp_avg = sum(list_tc_temp) / len(list_tc_temp)
                    tc_temp_max = max(list_tc_temp)
                    pwm_width_s = self.get_pwm_width(self.target_temp, tc_temp_max, max_q0, max_q49, dtemp50dv_max)  #{210118} temporal logic
                else:
                    pwm_width_s = 0
                
                if Debug4: print(f"debug_4 in ssr, SSR({self.pin_num}) Tc: {tc_temp_max:.2f}")
                
                self.set_pwm_width(pwm_width_s)
                # time.sleep(1)
            except KeyboardInterrupt:
                print (f'exiting thread-1 in temp_read({self.pin_num})')
                self.close()

            
        print(f"exit SSR: {self.pin_num}")

  
    def get_pwm_width(self, target_temp, tc_temp, max_q0, max_q49, d_temp50dv_max):
        """
            PWM幅の計算
            P制御：設定温度との温度差 * 0.1
            I制御：未実装
            D制御：(d_temp = 微係数をつかう)
            
        """
        
        """
        時刻の増加のシーケンスで、dt を計算するときは
        59.8, 59.9, 60.0,  0.1, 数字が下がったら、60を加えて、
                          60.1 として引き算する,
                          
        """

        if self.d_temp is None:
            self.d_temp = target_temp - tc_temp
            
        if self.pin_num == 2 :
             print("get_pwm_width for SSR with logic at pin of", self.pin_num)
        if self.pin_num == 3 :
             pass
        if self.pin_num == 4 :
             pass
        if self.pin_num == 9 :
             pass    
        if Debug3: 
           print("dddddddddddd  SSR, self.pin_num=",self.pin_num)           

        dtemp_t=dtemp_total=target_temp-room_temp   
        
        target_temp_s=target_temp_scaled =(
                      target_temp-room_temp)/dtemp_t
                      
        tc_temp_s    =tc_temp_scaled     =(
                      tc_temp-room_temp)/dtemp_t

        d_temp_s=self.d_temp/dtemp_t
        ########
        if Debug1: print("~~~ debug in ssr, tc_temp_s=",tc_temp_s)
        if Debug1: print("                  tc_temp, target_temp, room_temp=",tc_temp, target_temp, room_temp)
       

        # BEGIN　 SSR(n)の制御ロジック
        
        
        """
        {210203}
        target_temp_sについて、２つ持っておく。
        ひとつは、熱電対で監視している、部署の、最大の温度
        ひとつは、温度指定した実験のため、あるターゲット温度にしたい部位。
        """
        
        ki_II=0
        kp_II=0
        kd_II=0
        if not ((max_q0 == None) or (max_q49 == None)):
          print("max_q0, max_q49=",max_q0, max_q49, "    {210124C}")
          dt=50
          print("dt, ki,  d_temp50dv_max=",dt, ki, d_temp50dv_max)
          ki_II=ki*(((target_temp_s - max_q49/dtemp_t) + (target_temp_s - max_q0/dtemp_t))*0.5 )*dt
          self.d_temp_s=self.d_temp_scaled =(self.d_temp)/dtemp_t
          kp_II= self.kp*(target_temp_s-tc_temp_s)
          kd_II= 0
          if self.pin_num==2:
            print ("ki_II=",ki_II)
            print ("kp_II=",kp_II)
          
                      
        pwm_width_s_2 = ki_II - kp_II
        if self.pin_num==2:
          if pwm_width_s_2 < 0:
            print("pwm_width_s_2 is negative, self.pin_num=",self.pin_num)
            pwm_width_s_2=0
          print("pwm_width_s_2=", pwm_width_s_2, "{210124D}")

        pwm_width_s = pwm_width_s_2
        
        """
        (psudo code)
        I-PD control logic
        {210121}
        ３つの異なる熱容量の物体が互いに接続しているので、方程式は3次と等価になる。
        １）加熱試験で、制御対象のモデル因子（resister, capaciter）を計測する。
        ２）ラプラス変換で、制御系が、妥当であることをあらかじめ確認する。
        ３）（できれば、規範モデル、に合わせるように、I-PD系を設計する）
        print(max(q[0]))
        print(max(q[49])
        dt=5.0 (second)
        I成分は（self.kI*）、+( ((target_temp_s - max(q[49])/dtemp_t)
                + (target_temp_s - max(q[0])/dtemp_t))/2 )*dt
        P成分は、-(tc_temp_s)*self.kp
        D成分は（self.kD*）、-(max(q[49])/dtemp_t - max(q[0])/dtemp_t)/dt
        （符号にきをつけよう）
        """              
        
        
        
        # END SSR(n)の制御ロジック



        # PWM幅を制限
        if pwm_width_s < 0.0:
            pwm_width_s = 0.0

        if pwm_width_s > 1.0:
            print("OBS! OBS! OBS! pwm_width_s > 1.0")
            pwm_width_s = pwm_width_s_max #OBS OBS maximum pwm_width to be safe {210203}


        #OBS! OBS!  ここは不要では？　　　二重になっているか？？
        # 温度差（将来のPID制御用）
        self.d_temp = target_temp - tc_temp
        #OBS! OBS!  ここは不要では？

        return pwm_width_s


#       
    def aaaa():  #{210201}
        pass


    def set_pwm_width(self, pwm_width_s):
        """
            PWMの出力
            on_time: ON時間
            off_time: OFF時間
        """
#        pwm_width_s=pwm_width_scaled=pwm_width / MAX_PWM_WIDTH

        pwm_width_s=pwm_width_scaled=pwm_width_s
        
        on_time  = pwm_total_time * pwm_width_s
        off_time = pwm_total_time * (1-pwm_width_s)
        if Debug6:
          if self.pin_num==2:
           print("+++ debug_6 in ssr, set_pwm_width",f"SSR({self.pin_num})",f"on: {on_time/pwm_total_time}, off: {off_time/pwm_total_time}")
        GPIO.output(self.pin_num, True)
        time.sleep(on_time)
        GPIO.output(self.pin_num, False)
        time.sleep(off_time)

        if Debug3: print("debug in ssr,", f"SSR({self.pin_num}) pwm_width_s = {pwm_width_s}")

    def set_target_temp(self, target_temp):
        self.target_temp = target_temp

    def set_kp(self, kp):
        self.kp = kp

    def close(self):
        """
        外部からSSR制御のスレッド停止用
        """
        print(f"close SSR: {self.pin_num}")
        self.running = False

