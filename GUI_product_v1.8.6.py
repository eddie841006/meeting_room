#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 10:58:38 2020

@author: c95hcw
"""
import shutil
from tkinter import Tk, Label, Button
from wave_cut import cut_wave
import wave
import time
import numpy as np
import pyaudio
import  tkinter as tk
import PIL  #,Image 
from PIL import ImageTk 

import os
import math
import glob
import re
import configparser
import json
import requests
import speech_recognition as sr
import librosa
import randomcolor
from playsound import playsound
import Levenshtein
import cocon_api
import recording_thread_multi_mic as rt

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
        self.start_time = ''  # Begin when streaming start
        self.BOS_time = ''  # Begin of Speech time
        self.EOS_time = ''  # End of Speech time
        self.click = 0
        # recording parameter
        self.stream = None
        self.frames= []
        self.start_index = []
        self.stop_index = []
        self.pa = pyaudio.PyAudio()
        self.recording_format = pyaudio.paInt16
        self.recording_chunk = 3024
        self.recording_sample_rate = 16000
        self.recording_channel = 1
        self.threshold = 300
        # output file name parameter
        self.date_folder_name=str(time.strftime("%Y_%m_%d", time.localtime()))
        self.meeting_time = str(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()))
        self.save_wave_name = ''
        self.save_label_name = ''
        self.save_label_content = ''
        self.save_label_time = ''
        self.save_txt = ''
        self.save_sum = ''

        self.label_speaker_list = []
        self.label_asr_list = []

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

        # 圖形化介面錄音按鈕左側的小按鈕，按下後會將所有已啟動的麥克風關閉
        self.button_reset_connection = Button(self.top_frame, image=None, command=self.resetConnection)

        # ============ disable the button
        if config['demo_mode'].get('input_mode') == 'wave':
            self.button_stop = Button(self.top_frame,image=self.play_wav_im, command=None) # self.stopRecordingMandotorily
        if config['demo_mode'].get('input_mode') == 'record':
            self.button_stop = Button(self.top_frame,image=self.stop_im, command=None) # self.stopRecordingMandotorily
        self.button_stop.pack(side='right')

        self.button_start = Button(self.top_frame,image=self.reco_im, command=None)
        self.button_start.pack(side='right')

        self.button_reset_connection.pack(side='right')

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

        self.wave_name_generate()
        if config['demo_mode'].get('input_mode') == 'wave':
            self.button_start.config(state = 'disabled')

        self.gui = None
        self.num_of_mic = 10 #
        # 2支麥克風共用1個本機音訊裝置e.g.: 1號和2號使用"DVS Receive 1-2"
        self.num_of_device = math.ceil(self.num_of_mic / 2)

        # 記錄所有麥克風資訊，mic_dict {"device_index": 音源裝置(麥克風)系統編號, "thread": 紀錄音訊串流(麥克風聲音)以及處理切音的執行緒}
        self.mic_list = self.createMic()

        self.cocon = None

        # 紀錄當前已啟動的麥克風
        self.activated_mic_set = set()
        self.mic_thread_list = [None] # list[0] is None


    def createMic(self):
        # mic_list = [None]
        mic_list = []
        for i in range(1, self.num_of_mic + 1):
            mic_object = Microphone(i, None, None)
            mic_list.append(mic_object)

        mic_device_name = ['DVS Receive  1-2 (Dante Virtual', 'DVS Receive  3-4 (Dante Virtual', 'DVS Receive  5-6 (Dante Virtual']
        mic_device_name += ['DVS Receive  7-8 (Dante Virtual', 'DVS Receive  9-10 (Dante Virtua']

        # 2支麥克風共用1個本機音訊裝置e.g.: 1號和2號使用"DVS Receive 1-2"
        # 製作音訊裝置名稱對應麥克風編號list的字典
        mic_num_dev_name_dict = {}

        ctr = 1
        for device_name in mic_device_name:
            mic_num_list = []
            for i in range(ctr, ctr+2):
                # 如果麥克風數量是奇數
                if i > len(mic_list):
                    i = len(mic_list) - 1
                mic_num_list.append(i)

            mic_num_dev_name_dict[device_name] = mic_num_list
            ctr+=2

        print("====== Audio device information ======")
        try:
            for i in range(30):
                device_dict = self.pa.get_device_info_by_index(i)

                if device_dict["name"] in mic_num_dev_name_dict.keys():
                    mic_num_list = mic_num_dev_name_dict[ device_dict["name"] ]
                    for mic_num in mic_num_list:
                        mic_list[mic_num-1].device_number = i

        except:
            pass

        # 印出所有麥克風資訊
        for mic in mic_list:
            print(f"mic num: {mic.mic_number}, device_number: {mic.device_number}, recording_thread: {mic.recording_thread}")

        return mic_list

    def storeSelfGUIObject(self, gui):
        self.gui = gui

    def storeCoconObject(self, cocon):
        self.cocon = cocon

    # reset connection manually
    def resetConnection(self):
        self.cocon.createControlConnection()
        self.cocon.disableMic(self.activated_mic_set)

    def createMicThread(self):
        if config['demo_mode'].get('input_mode') == 'record':
            if self.gui is not None:
                try:
                    # 為每一個音訊裝置產生一個執行緒
                    ctr = 1
                    for i in range(1, self.num_of_device+1):
                        # mic_number, mic_device_index, gui
                        thread = rt.RecordingThread(self.mic_list[ctr-1].device_number, self.gui)
                        thread.setDaemon(True)
                        thread.start()
                        for j in range(ctr, ctr+2):
                            if j > len(self.mic_list):
                                j = len(self.mic_list)-1

                            self.mic_list[j-1].recording_thread = thread

                        ctr += 2

                except Exception as e:
                    print(e)
                    exit(0)

            else:
                print("Error: gui object is none.")


    def pressMic(self, mic_number):

        self.mic_list[mic_number-1].recording_thread.press_button_play(mic_number)

        self.activated_mic_set.add(mic_number)

    def shutdownMic(self, mic_number):

        if config['demo_mode'].get('input_mode') == 'record':
            self.swith_button_status('stop')
            self.activated_mic_set.remove(mic_number)

            self.mic_list[mic_number - 1].recording_thread.press_button_stop(mic_number, self.record_num, self.threshold)

            self.record_num += 1

        if config['demo_mode'].get('input_mode') == 'wave':
            self.button_stop.config(state='disabled')
            waves_path = config['demo_mode'].get('wave_files')
            all_wav = sorted(glob.glob(os.path.join(waves_path + "/*.wav")))
            wav_len = len(all_wav)
            if wav_len != 0:
                for sub_wave_name in all_wav:
                    print(sub_wave_name)
                    playsound(sub_wave_name)
                    self.recognitions(sub_wave_name)
                    print(self.record_num)
                    self.record_num += 1
                    self.read_num += 1
            self.button_stop.config(state='active')


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


    def wave_name_generate(self):
        # date dir generate
        if not os.path.isdir(self.date_folder_name):
            os.mkdir(self.date_folder_name)
        # author dir generate
        self.record_folder = self.date_folder_name 

        # output file: full path for wave and label name
        self.save_wave_name = self.record_folder  + "/" + self.meeting_time + "_record_original.wav"
        self.save_label_name = self.record_folder  + "/" + self.meeting_time + "_record_original.txt"

    def save_wav(self,save_name,save_frames):

        wf = wave.open(save_name, 'wb')
        wf.setnchannels(self.recording_channel)
        wf.setsampwidth(2)
        wf.setframerate(self.recording_sample_rate)
        print('after sample rate = ' + str(wf.getframerate()))
        wf.writeframes(np.array(save_frames).tostring())
        wf.close() 
            
    def speaker_id(self,wav_name):
        wav, sr = librosa.load(wav_name, sr=16000)
        url = "http://172.16.121.124:8002/ailab"
        text = {"speaker":wav.tolist()}
        a = requests.post(url,json=text)
        speaker = json.loads(a.text)["name"]
     
        # speaker = ""
        print(speaker)
        return speaker
    
    def speech_MASR(self,wave_path):
        
        with wave.open(wave_path) as wav:
            wav = np.frombuffer(wav.readframes(wav.getnframes()), dtype="int16")
            wav = wav.astype("float")                
        wav = (wav - wav.mean()) / wav.std()

        url = "http://172.16.121.124:8001/MASR"
        waves = {"speech": wav.tolist()}   #spectrum頻譜
        rt = requests.post(url, json=waves)  #將list資料post至指定url的flask
        text = rt.text                          #rt回傳資料

        return text   

    
    def speech_google(self,wav_cnam):        
        # for google need audio_data
        result = ''
        with sr.WavFile(wav_cnam) as source:
                audio_data =sr.Recognizer().record(source)         
        try:
            result = sr.Recognizer().recognize_google(audio_data, language="zh-TW")
            print(result)                    
        except sr.UnknownValueError:
            result ="無法辨識"
            print('this utterance have some error w/ ' + str(sr.UnknownValueError))

        return result                
        
    def run_summary(self,content):
        if len(content) > 1:
            content="，".join(content)
        elif len(content) == 0:
            content = "無法辨識"
        else:
            content = content[0]
        content = re.sub(r'無法辨識，|，無法辨識$','',content)           
        url="http://172.16.121.124:7080/summarization"
        ttext={"text":content}
        print(ttext)
        s=requests.post(url,json=ttext)
        summary = s.text[:]
        
        if len(content)<=25:
            summary=str(content)       
        else:
            if summary=='':
                for ii in range(10):
                    if summary=='':                    
                        s=requests.post(url,json=ttext)
                        summary = s.text[:-1]
                        print(ii)                
                if summary=='':
                    summary="Null"
        search_meeting_annouce = re.search(r'會議(議|一)程.*主席.*投資.*討論.*共\d+分鐘', content)
        search_meeting_duration = re.search(r'共\d+分鐘', content)    
        if search_meeting_annouce: #1081219
            summary="會議議程" + search_meeting_duration.group()
        #summary = "123"        
        return summary

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

    def output_speech(self,speech_result):
        num_of_word_in_line = 25
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
        content_rows = int(len(speech)/num_of_word_in_line)
        remaining_words = len(speech)%num_of_word_in_line

        speech_index = "no different"        
        if  config['demo_mode'].get('input_mode') == 'wave':        
            speech_index = self.mappingtxtans(speech) 
            text_end_num = str(int(float(self.txt_dp2.index("end")))-1)

        if len(speech) <= num_of_word_in_line:
            result_o =  str(speech)  + "\n\n"
            content_rows = 1
        else: 
            results = []
            for i in range(0,content_rows):
                results.append(str(speech[num_of_word_in_line*i:num_of_word_in_line*(i+1):1])+"\n")
            result_all = "".join(results)
            if remaining_words == 0:            
                result_o = str(result_all) + "\n"    
            else:
                result_o = str(result_all)+str(speech[num_of_word_in_line*content_rows::1])+"\n"+"\n"
            content_rows = len(results) + 1            
        if self.record_num % 2 !=0 and config['demo_mode'].get('input_mode') == 'record':
            self.txt_dp2.tag_config('brown',foreground ='Brown')
            self.txt_dp2.insert(tk.END,str(result_o), 'brown')
        else:
            self.txt_dp2.insert(tk.END,str(result_o))#, 'greencolor'
            self.txt_dp2.tag_configure("red", foreground="red")
            if speech_index != "no different":
                print('11111')
                for x in speech_index:
                    if x >= num_of_word_in_line:
                        x = x - num_of_word_in_line
                    self.txt_dp2.tag_add("red", text_end_num + "." + str(x), text_end_num + "." + str(x + 1))
        self.txt_dp2.see(tk.END)
        self.master.update()

        return content_rows,result_o

   

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


    def recognitions(self,sub_wave_name):
        speaker = self.speaker_id(sub_wave_name)

        self.save_label_content += str(speaker) + ','
        self.label_speaker_list.append(str(speaker))

        self.save_file="save_audio" +  str(self.record_num)
        print("record_num: ",self.record_num)            
        cut_wave(sub_wave_name,self.save_file) 
        c_wav=sorted(glob.glob(os.path.join(self.save_file, '*.wav')))        
        speech_results = []
        speech_results2 = []
        for wav_cnam in c_wav:            
            if self.speech_mode == 'S1':
                speech = self.speech_MASR(wav_cnam)
                if speech != "":
                    speech_results.append(speech)

                
            if self.speech_mode == 'S2':
                speech = self.speech_google(wav_cnam)
                speech_results.append(speech)
        print(speech_results)
        content_rows,result = self.output_speech(speech_results)

        self.save_label_content += result
        self.label_asr_list.append(result)

        self.save_txt +=  speaker + "\t" + result + "\n"           
        if config['layout'].get('dp3') == 'summarization':
            summary = self.run_summary(speech_results)   
            self.output_summary(summary,content_rows)
            self.save_sum += speaker + "\t" + summary + "\n"
        self.output_speaker(speaker,content_rows)  
        self.master.update()
        shutil.rmtree(self.save_file)

    def press_button_clean(self):
        self.txt_dp3.delete('0.0',tk.END)
        self.txt_dp2.delete('0.0',tk.END)
        self.txt_speaker.delete('0.0',tk.END) 
            
    def swith_button_status(self,trigger):
        # dobule click check mechanism
        if  (trigger=='play' and str(self.button_start['state']) == 'disabled'): return
        if  (trigger=='stop' and str(self.button_stop['state']) == 'disabled'): return

        if trigger=='stop':
            self.button_stop.config(state = 'disabled')
            self.button_start.config(state = 'active')
        else:
            self.button_start.config(state = 'disabled')
            self.button_stop.config(state = 'active')
        self.master.update()

    def concatenateRecordFile(self):
        record_file_list = []
        # the folder temporarily saves the audios recorded by the microphones.
        # the folder will be cleared after all the audios are concatenated
        # to a audio file ([Date time]_record_original.wav) saved in record_folder (yyyy_mm_dd)
        record_file_path = "all_records"

        for root, dirs, files in os.walk(record_file_path):
            for f in files:
                record_file = os.path.join(record_file_path, f)
                # print(record_file)
                record_file_list.append(record_file)

        f1 = open(self.save_label_name, 'w', encoding='utf-8')

        audio_previous_time = 0.0

        if len(record_file_list) == len(self.label_speaker_list) == len(self.label_asr_list):

            data = []
            for f,speaker,asr in zip(record_file_list, self.label_speaker_list, self.label_asr_list):
                w = wave.open(f, 'rb')


                audio_duration = w.getnframes() / w.getframerate()
                audio_duration += audio_previous_time

                record_label_line = str(audio_previous_time) + "," + str(audio_duration) + "," + speaker + "," + asr # asr text has '\n'

                f1.write(record_label_line)

                audio_previous_time = audio_duration

                data.append([w.getparams(), w.readframes(w.getnframes())])
                w.close()

            output = wave.open(self.save_wave_name, 'wb')
            output.setparams(data[0][0])

            for i in range(len(data)):
                output.writeframes(data[i][1])

            output.close() # close audio file
            f1.close() # close label file

        else:
            print("Error: some label data is loss")

        try:
            for file in record_file_list:
                os.remove(file)
        except OSError as e:
            print(e)


    def on_closing(self):
        
        if config['demo_mode'].get('input_mode') == 'record':

            self.concatenateRecordFile()

            # record_folder: yyyy_mm_dd
            print("The meeting audio and label file have been saved.\nPlease check folder ", self.record_folder)

        if self.save_txt!='':
            save_txt_name = self.record_folder + "/" + self.meeting_time + '_會議逐字稿' +'.txt'
            f2 = open(save_txt_name, 'w', encoding='utf-8')
            f2.write(self.save_txt)
            f2.close()   

            if config['layout'].get('dp3') == 'summarization'  and  self.save_sum!='':
                save_sum_name = self.record_folder + "/" + self.meeting_time + '_會議紀錄摘要' +'.txt'
                f3 = open(save_sum_name, 'w', encoding='utf-8')
                f3.write(self.save_sum)
                f3.close()            
        self.master.destroy()

class Microphone():
    def __init__(self, mic_number, device_number, recording_thread):
        # 連接會議主機的麥克風編號，唯一編號，從1開始編
        self.mic_number = mic_number
        # 本機電腦識別的音訊裝置編號，2支麥克風會共用1個本機音訊裝置編號
        self.device_number = device_number
        # 紀錄語音訊號的執行緒，2支麥克風會共用1個執行緒
        self.recording_thread = recording_thread

def read_config():
    conf = configparser.ConfigParser()
    candidates = ['config_record_0922.ini']
    conf.read(candidates)
    return conf

if __name__== "__main__":
    config =read_config()
    root = Tk()
    my_gui = NCSISTGUI(root,config)
    my_gui.storeSelfGUIObject(my_gui)
    my_gui.createMicThread()

    cocon = cocon_api.CoConAPI(my_gui)

    my_gui.storeCoconObject(cocon)

    root.protocol("WM_DELETE_WINDOW", my_gui.on_closing)
    root.mainloop()
