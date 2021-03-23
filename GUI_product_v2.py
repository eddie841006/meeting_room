#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 10:58:38 2020

@author: c95hcw
"""
"""
    GUI每秒鐘向recording_server.py要求一個語音檔名，如果要到語音檔名，就讀取語音檔並傳送語音訊號給recognition_server等待辨識
"""

from tkinter import Tk, Button

import time
import  tkinter as tk
import PIL
from PIL import ImageTk
import re
import configparser
import json
import requests
import randomcolor
import Levenshtein
import threading
import meeting_record as mr
import librosa


recognition_server_ip_port = "http://127.0.0.1:3000"

recording_server_ip_port = "http://127.0.0.1:4000"

class NCSISTGUI:
    def __init__(self, master,config):
        self.master = master
        self.row_image1 = PIL.Image.open("./image/micro3.png").resize((70,70),PIL.Image.ANTIALIAS)
        self.row_image2 = PIL.Image.open("./image/pause3.png").resize((70,70),PIL.Image.ANTIALIAS)
        self.row_image3 = PIL.Image.open("./image/eraser2.png").resize((70,70),PIL.Image.ANTIALIAS)
        self.row_image4 = PIL.Image.open("./image/play_wav.png").resize((70,70),PIL.Image.ANTIALIAS)
        self.reco_im = ImageTk.PhotoImage(self.row_image1)  
        self.stop_im = ImageTk.PhotoImage(self.row_image2)  
        self.clean_im =ImageTk.PhotoImage(self.row_image3)
        self.play_wav_im = ImageTk.PhotoImage(self.row_image4)
        # buttom timing parameter

        self.click = 0

        self.record_num = 0
        self.read_num = 0
        self.speakers = []
        self.speaker_colors = []

        self.master.title(" NCSIST Meeting Record")
        self.master.resizable(False, False)
        
        # frame setting
        self.top_frame = tk.Frame(master, bg='Moccasin', width=900, height=50, pady=3)
        self.center_frame = tk.Frame(master, bg='FloralWhite', width=50, height=40, padx=3, pady=3)
        self.botton_frame = tk.Frame(master, bg='FloralWhite', width=50, height=40, padx=3, pady=3)
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        self.top_frame.grid(row=0, sticky="ew")
        self.center_frame.grid(row=1, sticky="nsew")
        self.botton_frame.grid(row=2,sticky="nsew")
        
        # topframe: operator
        self.l_subtitle = tk.Label(self.top_frame, text=" [NCSIST AI Lab]  Speech & Speaker Recognition ",bg='Moccasin', font=('Time news Roma', 25), anchor="n")
        self.l_subtitle.pack(side='left')        
        self.button_clean = Button(self.top_frame,image=self.clean_im, command=self.press_button_clean)
        self.button_clean.pack(side='right')

        # ============ disable the button
        if config['demo_mode'].get('input_mode') == 'wave':
            self.button_stop = Button(self.top_frame,image=self.play_wav_im, command=None)
        if config['demo_mode'].get('input_mode') == 'record':
            self.button_stop = Button(self.top_frame,image=self.stop_im, command=None)
        self.button_stop.pack(side='right')

        self.button_start = Button(self.top_frame,image=self.reco_im, command=None)
        self.button_start.pack(side='right')


        # center frame/bottom frame size setup
        dp1w = config['layout'].getint('dp1w')
        dp2w = config['layout'].getint('dp2w')
        dp3w = config['layout'].getint('dp3w')
        dph = config['layout'].getint('dph')
        dplabelh  = config['layout'].getint('dplabelh')
        dp2_width = dp2w+dp3w-500 if config['layout'].get('dp3') == 'none' else dp2w

        # center frame label
        self.frm_speaker_label = tk.Frame(self.center_frame,width = dp1w, height = dplabelh, bg = 'FloralWhite' ) # 100 900
        self.frm_speaker_label.grid(row=0,column=0,padx=2,pady=2,sticky="e")# sticky="ew"
        self.frm_speaker_label.grid_propagate(0)

        self.frm_speech_label = tk.Frame(self.center_frame,width = dp2_width, height =dplabelh, bg = 'FloralWhite') # 950 900
        self.frm_speech_label.grid(row=0,column=1,padx=2,pady=2,sticky="e")
        self.frm_speech_label.grid_propagate(0)
        
        l_speaker =  tk.Label(self.frm_speaker_label, text=" 發言者 ",bg='FloralWhite', font=('Time news Roma', 15))#,relief="raised"
        l_speaker.grid(row=0,column=0,sticky="nsew")

        # choose speech mode
        self.speech_mode =  config['layout'].get('mode')        
        if self.speech_mode == 'S1':
            l_speech =  tk.Label(self.frm_speech_label, text="發言內容",bg='FloralWhite', font=('Time news Roma', 15), anchor="s")#20 50
            l_speech.grid()    
        if self.speech_mode == 'S2':
            l_google = tk.Label(self.frm_speech_label, text="發言內容",bg='FloralWhite', font=('Time news Roma', 15))#20 50
            l_google.grid(row=0,column=0)


        #  choose dp3 mode       
        if config['layout'].get('dp3') == 'summarization': 
            self.frm_dp3 = tk.Frame(self.center_frame,width = dp3w, height = dplabelh, bg = 'FloralWhite') # 720 900
            self.frm_dp3.grid(row=0,column=2)
            self.frm_dp3.grid_propagate(0)
            l_summ =  tk.Label(self.frm_dp3, text=" 摘要內容 ",bg='FloralWhite', font=('Time news Roma', 15), anchor="n")#20 50
            l_summ.grid(row=0,column=0)

        # Scrollbar       
        self.vsb_frm = tk.Frame(self.botton_frame,width=20, height = dph)#,highlightthickness= 2
        if config['layout'].get('dp3') == 'none': 
            self.vsb_frm.grid( row =0, column =2, sticky="nse") 
        else:
            self.vsb_frm.grid(row=0,column=3, sticky="nse")
        self.vsb_frm.pack_propagate(0)
        self.vsb = tk.Scrollbar(self.vsb_frm,width=20,orient="vertical",command=self.OnVsb)#
        # self.vsb.grid(row =0, column =0,sticky="nse")
        self.vsb.pack(side='right',fill='y')
        

        # bottom frame 'spearker - masr - google - summarization
        self.frm_speaker = tk.Frame(self.botton_frame,width = dp1w, height = dph, bg = 'FloralWhite',highlightthickness= 2 ) # 100 900
        self.frm_speaker.grid(row=0,column=0)
        self.frm_speaker.grid_propagate(0)
        
        self.txt_speaker = tk.Text(self.frm_speaker,yscrollcommand=self.vsb.set, bg = 'FloralWhite', font=('Time news Roma', 20))#,yscrollcommand=vsb.set
        self.txt_speaker.grid()

        
        self.frm_speech = tk.Frame(self.botton_frame,width = dp2_width, height =dph, bg = 'FloralWhite',highlightthickness= 2) # 950 900
        self.frm_speech.grid(row=0,column=1)
        self.frm_speech.grid_propagate(0)
        self.txt_dp2 = tk.Text(self.frm_speech ,yscrollcommand=self.vsb.set, bg = 'FloralWhite', font=('Time news Roma', 20))#,yscrollcommand=vsb.set
        self.txt_dp2.grid(row=0,column=0)

            
        if config['layout'].get('dp3') == 'summarization' :  
            self.frm_dp3 = tk.Frame(self.botton_frame,width = dp3w, height = dph, bg = 'FloralWhite',highlightthickness=2) # 720 900
            self.frm_dp3.grid(row=0,column=2)
            self.frm_dp3.grid_propagate(0)
            self.txt_dp3 = tk.Text(self.frm_dp3 ,yscrollcommand=self.vsb.set, bg = 'FloralWhite', font=('Time news Roma', 20))#
            self.txt_dp3.grid(row=0,column=0)    

        self.txt_dp2.bind("<MouseWheel>", self.OnMouseWheel)
        self.txt_speaker.bind("<MouseWheel>",self.OnMouseWheel)
        if config['layout'].get('dp3') != 'none':
            self.txt_dp3.bind("<MouseWheel>", self.OnMouseWheel)

        if config['demo_mode'].get('input_mode') == 'wave':
            self.button_start.config(state = 'disabled')

        # 儲存要辨識的音檔
        self.meeting_record_audio_list = []

        # 建立儲存會議記錄的物件，GUI關閉時會呼叫meeting_record的函式儲存會議紀錄
        self.meeting_record = mr.MeetingRecord()

        # 呼叫recording_server初始化要辨識的音檔清單
        self.initialize_recog_audio_list()

    # 向recording_server.py要一個音檔名稱
    def initialize_recog_audio_list(self):
        try:
            url = recording_server_ip_port + "/initializeRecogAudioList"
            resp = requests.post(url)
            return_value = json.loads(resp.text)["return_value"]
            if return_value == 1:
                print("初始化要辨識的音檔清單 成功")
            else:
                print("初始化要辨識的音檔清單 失敗")
        except:
            print("Recording Server未開啟")
            print("python recording_server.py")
            exit(0)

    def OnVsb(self,*args):
       self.txt_dp2.yview(*args)
       self.txt_speaker.yview(*args)
       if config['layout'].get('dp3') == 'summarization':  
            self.txt_dp3.yview(*args)
       
    def OnMouseWheel(self, event):
        self.txt_dp2.yview("scroll", event.delta,"units")
        self.txt_speaker.yview("scroll", event.delta,"units")
        if config['layout'].get('dp3') == 'summarization':
            self.txt_dp3.yview("scroll", event.delta,"units")

        return "break"

    def mappingtxtans(self,speech_results):
        ans_txt = config['Answer'].get('ans_txt')
        f = open(ans_txt)
        text = []
        for line in f:
            text.append(line.rstrip())
        print(text)
    
        if self.read_num > len(text):
             self.read_num == 0
    
        txt_ans = text[self.read_num]
        speech_ans_list = list(speech_results)
        speech_ans_range = range(len(speech_ans_list))
        e = Levenshtein.editops(txt_ans, speech_results)
        index = []
        com = '，'
        com_index = speech_results.find(com)        
        e = list(filter(lambda x: x[0] != 'delete', e))
        for item in e:
            if item[2] != com_index:
                index.append(item[2])        
        if index == []:
            return "no different"
        else:
            return index
    # 輸出語音辨識結果到介面上
    def output_speech(self,speech_result):
        num_of_word_in_line = 25 # 每列字數限制
        if len(speech_result) > 1:
            speeches = []
            for text in speech_result:
                if text != '':
                    speeches.append(text)
            speech ="，".join(speeches)
        elif len(speech_result) == 1:
            speech = speech_result[0]
        else:
            speech = "無法辨識"
        speech = re.sub(r'無法辨識，|，無法辨識$','',speech)           
        content_rows = int(len(speech)/num_of_word_in_line) # 語音辨識顯示GUI列數
        remaining_words = len(speech)%num_of_word_in_line # 判斷是否換下列(整除列數=content_rows,不整除列數=content_rows+1)

        speech_index = "no different"        
        if  config['demo_mode'].get('input_mode') == 'wave':        
            speech_index = self.mappingtxtans(speech) 
            text_end_num = str(int(float(self.txt_dp2.index("end")))-1)

        if len(speech) <= num_of_word_in_line:
            result_o =  str(speech)  + "\n\n"
            content_rows = 1
        else: 
            results = [] # 總句數
            for i in range(0,content_rows):
                results.append(str(speech[num_of_word_in_line*i:num_of_word_in_line*(i+1):1])+"\n")
            result_all = "".join(results)
            if remaining_words == 0:            
                result_o = str(result_all) + "\n"
                content_rows = len(results)
            else:
                result_o = str(result_all)+str(speech[num_of_word_in_line*content_rows::1])+"\n"+"\n"
                content_rows = len(results) + 1
        if self.record_num % 2 !=0 and config['demo_mode'].get('input_mode') == 'record':
            self.txt_dp2.tag_config('brown',foreground ='Brown')
            self.txt_dp2.insert(tk.END,str(result_o), 'brown')
        else:
            self.txt_dp2.insert(tk.END,str(result_o))#, 'greencolor'
            self.txt_dp2.tag_configure("red", foreground="red")
            if speech_index != "no different": # (wave mode)對正確答案,錯誤字以紅色標記
                print('11111')
                for x in speech_index:
                    if x >= num_of_word_in_line:
                        x = x - num_of_word_in_line
                    self.txt_dp2.tag_add("red", text_end_num + "." + str(x), text_end_num + "." + str(x + 1))
        self.txt_dp2.see(tk.END)
        self.master.update()

        return content_rows,result_o

    # 輸出摘要到介面上
    def output_summary(self,summary,content_rows):
        num_word = 25
        summ_rows = len(summary) // num_word
        remaining_words = len(summary)%num_word

        if len(summary) <= num_word:
            if content_rows == 1:
                summary_o =  str(summary)  + "\n"+"\n"
            else:
                summary_o =  str(summary)  + ("\n")*(content_rows+1)
        else:
            results = []
            for i in range(0,summ_rows):
                results.append(str(summary[num_word*i:num_word*(i+1):1])+"\n")
            result_all = "".join(results)
            if remaining_words == 0:
                summary_o = str(result_all) + ("\n")*(content_rows-summ_rows+1)
            else:
                summary_o = str(result_all)+str(summary[num_word*summ_rows::1])+("\n")*(content_rows-summ_rows+1)

        if self.record_num % 2 !=0 and config['demo_mode'].get('input_mode') == 'record':
            self.txt_dp3.tag_config('brown',foreground ='Brown')
            self.txt_dp3.insert(tk.END,summary_o, 'brown')
        else:   
            self.txt_dp3.insert(tk.END,summary_o, 'greencolor')
        self.txt_dp3.see(tk.END)
        self.master.update()

    # 輸出語者到介面上
    def output_speaker(self,speaker,content_rows):
        
        speaker_is_av = [name for name in self.speakers if speaker in name]
        rand_color = randomcolor.RandomColor()
    
        if speaker_is_av == [] :
            self.speakers.append(speaker)                   
            self.speaker_colors.append(rand_color.generate(luminosity='dark'))
            
        if content_rows == 1:
            speaker_o = speaker  +""+ "\n"+ "\n"
       
        elif content_rows > 1:
            speaker_o = speaker  +""+ (("\n")*(content_rows+1))
    
        self.color = dict(zip(self.speakers, self.speaker_colors))   
        s_color=self.color[speaker]
        s_color="".join(s_color)
        self.txt_speaker.tag_config(speaker,foreground =s_color)
        self.txt_speaker.insert(tk.END,speaker_o, speaker)
        self.txt_speaker.see(tk.END)
        self.master.update()

    # 將辨識結果呈現在GUI上
    def showRecognizedResult(self, recognized_result_dict, saving_flag):
        if "speech" in recognized_result_dict.keys():
            speech = recognized_result_dict["speech"]
            content_rows, result = self.output_speech(speech)


        if "speaker" in recognized_result_dict.keys():
            speaker = recognized_result_dict["speaker"]
            self.output_speaker(speaker, content_rows)

        if "summary" in recognized_result_dict.keys():
            summary = recognized_result_dict["summary"]
            self.output_summary(summary, content_rows)

        # 如果recognition_server沒有開啟，會進到這個block
        if saving_flag:
            speech = "".join(speech)
            self.meeting_record.saveMasrResult(speaker, speech)
            self.meeting_record.saveSummary(speaker, summary)

        self.master.update()

    def press_button_clean(self):
        self.txt_dp3.delete('0.0',tk.END)
        self.txt_dp2.delete('0.0',tk.END)
        self.txt_speaker.delete('0.0',tk.END)

    # 當使用者點擊GUI上的"關閉"(X)時，會進入此函式
    def on_closing(self):
        print("即將關閉GUI ...")
        print("將會議記錄寫檔")

        # 串接音檔並製作語音時間標記檔
        self.meeting_record.concatenateRecordFile(self.meeting_record_audio_list)

        # 寫入會議記錄至YYYY-MM-DD_meeting/
        self.meeting_record.writeMeetingRecord()

        # 初始化會議紀錄
        self.meeting_record.clearRecord()
        self.master.destroy()

    # 儲存自己的物件
    def storeSelfGUIObject(self, gui):
        self.gui = gui

# 如果從recording_server要到檔名時，傳送語音訊號給recognition_server
class RecognitionThread(threading.Thread):

    def __init__(self, gui, duration=1):
        threading.Thread.__init__(self)
        self.gui = gui
        self.duration = duration

    def run(self):
        request_audio_time = time.time()

        while True:
            if (time.time()-request_audio_time) >= self.duration:
                # 每秒鐘向recording_server要音檔
                url = recording_server_ip_port + "/getAudio"
                resp = requests.post(url)
                resp_dict = json.loads(resp.text)

                # 如果有收到最新的音檔
                if "audio_file" in resp_dict.keys():
                    audio_file = resp_dict["audio_file"]

                    # 傳送語音訊號給recognition_server等待辨識
                    try:

                        url = recognition_server_ip_port + "/postAudioFile"

                        wav, sr = librosa.load(audio_file, sr=16000)

                        data = {"wav": wav.tolist(), "sr": sr}
                        resp = requests.post(url, json=data)
                        # 接收recognition_server回傳的辨識結果
                        resp_dict = json.loads(resp.text)
                        # 呈現辨識結果到介面上
                        self.gui.showRecognizedResult(resp_dict, True)
                        # 紀錄要製作會議逐字稿的檔案清單
                        self.gui.meeting_record_audio_list.append(audio_file)
                        print(f"audio {audio_file}")

                    except:
                        # 如果recognition_server沒有開啟，會進到這個block
                        print("Recognition Server未開啟")
                        print("python recognition_server.py")
                        data = {}
                        data["speaker"] = ""
                        data["speech"] = ["Recognition Server未開啟"]
                        data["summary"] = ""
                        self.gui.showRecognizedResult(data, False)

                request_audio_time = time.time()

# 讀取GUI設定檔
def read_config():
    conf = configparser.ConfigParser()
    candidates = ['config_record_0922.ini']
    conf.read(candidates)
    return conf

if __name__== "__main__":
    # 讀取GUI設定檔
    config = read_config()
    root = Tk()
    # 初始化GUI
    my_gui = NCSISTGUI(root,config)

    my_gui.storeSelfGUIObject(my_gui)

    # 建立執行緒，每隔一段固定時間向recording_server要求一個語音檔名
    # 如果要到語音檔名，就讀語音檔並傳送語音訊號給recognition_server等待辨識
    recog_thread = RecognitionThread(my_gui)
    recog_thread.setDaemon(True)
    recog_thread.start()

    # 開啟GUI
    root.protocol("WM_DELETE_WINDOW", my_gui.on_closing)
    root.mainloop()
