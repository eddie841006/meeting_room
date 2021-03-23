import shutil
from wave_cut import cut_wave
import wave
import numpy as np
import pyaudio
import  tkinter as tk
import PIL  #,Image
from PIL import ImageTk
import datetime
import os
import sys
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
import threading
import time

class RecordingThread(threading.Thread):

    def __init__(self, mic_number, mic_device_index, gui):
        threading.Thread.__init__(self)

        self.gui = gui
        self.mic_number = mic_number
        self.mic_device_index = mic_device_index
        # buttom timing parameter
        self.start_time = ''  # Begin when streaming start
        self.BOS_time = ''  # Begin of Speech time
        self.EOS_time = ''  # End of Speech time
        self.click = 0
        # recording parameter
        self.stream = None
        self.frames = []
        self.start_index = []
        self.stop_index = []
        self.pa = pyaudio.PyAudio()
        self.recording_format = pyaudio.paInt16
        self.recording_chunk = 3024
        self.recording_sample_rate = 16000
        self.recording_channel = 1

        # output file name parameter
        self.date_folder_name = str(time.strftime("%Y_%m_%d", time.localtime()))
        self.meeting_time = str(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()))
        self.save_wave_name = ''
        self.save_label_name = ''
        self.save_label_content = ''
        self.save_label_time = ''
        self.save_txt = ''
        self.save_sum = ''

        self.thread_record_num = 0
        self.read_num = 0

    def press_button_play(self):
        print("mic number %d, device index %d press play " % (self.mic_number, self.mic_device_index))

        self.BOS = datetime.datetime.now()

        self.BOS_duration = (self.BOS - self.start_time).total_seconds()
        print('\tPress time: ' + str(self.BOS_duration))

        self.start_index.append(len(self.frames))

        self.gui.swith_button_status('play')

    def press_button_stop(self, all_record_num, threshold):
        print("mic number %d, device index %d press stop" % (self.mic_number, self.mic_device_index))

        self.EOS = datetime.datetime.now()  # 獲取當前時間

        self.EOS_duration = (self.EOS - self.BOS).total_seconds() # 紀錄錄音片段時間
        print('---- stop time = ' + str(self.EOS))
        print("已錄時間： ", self.EOS_duration)

        self.stop_index.append(len(self.frames))

        # 存單一音檔
        single_frame = self.frames[self.start_index[self.thread_record_num]:self.stop_index[self.thread_record_num]]

        sub_wave_name = "all_records/" + str(all_record_num) + '.wav'

        # self.gui.save_wav(sub_wave_name, single_frame)

        with wave.open(sub_wave_name) as wav:
            wav = np.frombuffer(wav.readframes(wav.getnframes()), dtype="int16")
            wav = wav.astype("float")
            num = np.sum(abs(wav))
            try:
                max_data = int((num / len(wav)))
            except:
                max_data = 0
            print('wave_avg/threshold:', max_data, '(', threshold, ')')

        # if max_data >= threshold:
        #     self.gui.recognitions(sub_wave_name)
        # else:
        #     # remove the audio whose volume does not over the threshold, which avoids the label loss
        #     try:
        #         os.remove(sub_wave_name)
        #     except OSError as e:
        #         print(e)
        #
        # self.thread_record_num += 1

    def run(self):

        print("*** Recording thread: ", self.mic_number, self.mic_device_index)
        self.stream = self.pa.open(format=self.recording_format, channels=self.recording_channel, rate=self.recording_sample_rate, input=True, input_device_index = 1, frames_per_buffer=self.recording_chunk)
        #self.stream = self.pa.open(format=self.recording_format, channels=self.recording_channel, rate=self.recording_sample_rate, input=True, frames_per_buffer=self.recording_chunk)

        self.stream.start_stream()

        self.start_time = datetime.datetime.now()

        start_time = time.time()
        while True:
            data = self.stream.read(self.recording_chunk, exception_on_overflow = False)
            # print(f"data size {sys.getsizeof(data)}")
            # exit(0)
            # break
            if time.time() - start_time() == 5:
                break
            self.frames.append(data)



if __name__ == "__main__":


    thread1 = RecordingThread(1, None, None)
    thread1.setDaemon(True)
    thread1.start()


