
"""

    recording_thread_multi_mic.py 由 recording_server.py 呼叫，負責從一張音效卡錄製語音訊號，功能如下:
    1. 持續監聽並抓取音效卡的語音訊號frame
    2. 等待recording_server呼叫press_button_play存放起始的frame index
    3. 等待recording_server呼叫press_button_stop存放結束的frame index，然後擷取一段語音訊號再存音檔(資料夾YYYY_MM_DD_audios/)

"""


import wave
import numpy as np
import pyaudio
import datetime
import os
import threading
import time as time

class RecordingThread(threading.Thread):

    def __init__(self, mic_device_index, mic_record, copied_audio_folder):
        threading.Thread.__init__(self)
        # recording_server.py的MicrophoneRecordingThread物件
        self.mic_record = mic_record
        # 音訊裝置編號
        self.mic_device_index = mic_device_index
        # 存放音檔的資料夾
        self.copied_audio_folder = copied_audio_folder

        # buttom timing parameter
        self.start_time = datetime.datetime.now()#''  # Begin when streaming start
        self.BOS_time = ''  # Begin of Speech time
        self.EOS_time = ''  # End of Speech time

        # recording parameter
        self.stream = None
        # 存放各聲道錄製的語音frame
        self.frames = [[], []]
        # 存放各聲道的起始語音frame index
        self.start_index = [[], []]
        # 存放各聲道的結束語音frame index
        self.stop_index = [[], []]

        self.pa = pyaudio.PyAudio()
        self.recording_format = pyaudio.paInt16
        self.recording_chunk = 2048
        self.recording_sample_rate = 16000
        # 設定錄音用的頻道數2，一張音效卡是雙聲道，1個聲道傳來1個麥克風的訊號
        self.recording_channel = 2
        # 設定音量閾值，如果音量低於該值，就不存音檔
        self.threshold = 300
        # 存放各聲道錄製的擷取語音段的數量
        self.thread_record_num = [0, 0]

    def initializeFrameList(self):
        self.frames = [[], []]

    # 決定聲道編號，麥克風編號偶數為1，奇數為0
    def determineChannelNumber(self, mic_number, status):
        # 麥克風偶數，channel編號為 1
        if mic_number % 2 == 0:
            self.channel1_status = status
            spec_channel = 1
        else:
            self.channel0_status = status
            spec_channel = 0

        return spec_channel

    # 存音檔
    def save_wav(self, save_name, save_frames):
        print(f"=== save wav === {save_name}")
        wf = wave.open(save_name, 'wb')
        # 存音檔要用單頻道存，因為單一支麥克風只用1個頻道
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(self.recording_sample_rate)
        print('after sample rate = ' + str(wf.getframerate()))
        wf.writeframes(np.array(save_frames).tostring())
        wf.close()
        print("=== end save wav ===")

    # 存放起始的frame index
    def press_button_play(self, mic_number):
        spec_channel = self.determineChannelNumber(mic_number, True)

        print("mic number %d, device index %d press play " % (mic_number, self.mic_device_index))
        print(f"channel {spec_channel}")

        self.BOS = datetime.datetime.now()

        self.BOS_duration = (self.BOS - self.start_time).total_seconds()
        print('\tPress time: ' + str(self.BOS_duration))

        self.start_index[spec_channel].append(len(self.frames[spec_channel]))

    # 存放結束的frame index，然後擷取一段語音訊號再存音檔
    def press_button_stop(self, mic_number, record_num):
        spec_channel = self.determineChannelNumber(mic_number, False)
        print("mic number %d, device index %d press stop" % (mic_number, self.mic_device_index))
        print(f"get channel {spec_channel} data")


        self.EOS = datetime.datetime.now()  # 獲取當前時間

        self.EOS_duration = (self.EOS - self.BOS).total_seconds() # 紀錄錄音片段時間
        print('---- stop time = ' + str(self.EOS))
        print("已錄時間： ", self.EOS_duration)

        self.stop_index[spec_channel].append(len(self.frames[spec_channel]))

        # 擷取語音訊號frame
        single_frame = self.frames[spec_channel][ self.start_index[spec_channel][ self.thread_record_num[spec_channel] ]:self.stop_index[spec_channel][ self.thread_record_num[spec_channel] ] ]
        # 將該頻道儲存的語音frame初始化為空list，避免記憶體容量不足
        self.frames[spec_channel] = []
        sub_wave_name = self.copied_audio_folder + str(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())) + "_" + str(record_num) + ".wav"

        # 存音檔
        self.save_wav(sub_wave_name, single_frame)

        with wave.open(sub_wave_name) as wav:
            wav = np.frombuffer(wav.readframes(wav.getnframes()), dtype="int16")
            wav = wav.astype("float")
            num = np.sum(abs(wav))
            try:
                max_data = int((num / len(wav)))
            except:
                max_data = 0
            print('wave_avg/threshold:', max_data, '(', self.threshold, ')')

        # 檢查音量是否有超過閾值
        if max_data >= self.threshold:

            # GUI有開啟的狀態，recognition_audio_list就不為None
            if self.mic_record.recognition_audio_list is not None:
                # 將音檔名稱存進recognition_audio_list，等待GUI向recording_server.py拿取
                self.mic_record.recognition_audio_list.append(sub_wave_name)
                print("recognition_audio_list: ", self.mic_record.recognition_audio_list)
        else:
            # 移除音量不足的音檔
            try:
                os.remove(sub_wave_name)
            except OSError as e:
                print(e)
        # 將該聲道擷取語音段的數量加1
        self.thread_record_num[spec_channel] += 1

    # 執行緒持續監聽並擷取音效卡的語音frame
    def run(self):
        print("*** Recording thread: ", self.mic_device_index)
        self.stream = self.pa.open(format=self.recording_format, channels=self.recording_channel, rate=self.recording_sample_rate, input=True, input_device_index=self.mic_device_index, frames_per_buffer=self.recording_chunk)

        self.stream.start_stream()

        self.start_time = datetime.datetime.now()

        while True:
            # 擷取frame
            data = self.stream.read(self.recording_chunk, exception_on_overflow = False)
            # 轉換成int
            indata = np.fromstring(data, dtype='int16')
            # 每間隔2取frame資料存入各別聲道frame list
            channel0 = indata[0::2].tobytes()
            channel1 = indata[1::2].tobytes()
            self.frames[0].append(channel0)
            self.frames[1].append(channel1)
