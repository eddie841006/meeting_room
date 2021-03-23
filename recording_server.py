
"""
    此程式要用系統管理員身分的命令提示字元執行
    recording_server.py是獨立的flask API server，功能如下:
    1. 呼叫cocon_api.py建立擷取網路封包的執行緒
    2. 呼叫recording_thread_multi_mic.py為每張Dante音效卡建立錄音執行緒，每張音效卡是雙聲道，2支麥克風訊號共用一個音效卡傳輸語音訊號，1支麥克風用一個聲道
    3. GUI剛開啟的時候呼叫API /initializeRecogAudioList 初始化recognition_audio_list，存放待會要拿取的音檔
    4. GUI每隔固定時間呼叫API /getAudio 拿取一個音檔名稱

    預先初始化的值:
        麥克風數量
            self.num_of_mic = 10
        音訊裝置名稱(Dante音效卡)，注意!! "DVS Receive  9-10 (Dante Virtua" 沒有 "l"
            mic_device_name = ['DVS Receive  1-2 (Dante Virtual', 'DVS Receive  3-4 (Dante Virtual', 'DVS Receive  5-6 (Dante Virtual']
            mic_device_name += ['DVS Receive  7-8 (Dante Virtual', 'DVS Receive  9-10 (Dante Virtua']
"""

from flask import Flask, jsonify, request
import math
import time as time
import pyaudio as pyaudio
import os
import threading
import recording_thread_multi_mic as rt
import cocon_api as cocon_api

app = Flask(__name__)
# app.config["DEBUG"] = True

#
class MicrophoneRecordingThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        # 設定有10支麥克風
        self.num_of_mic = 10
        # 2支麥克風共用1個Dante音效卡 e.g. 麥克風1號和2號使用"DVS Receive 1-2"
        # 計算有多少個要使用的Dante音效卡
        self.num_of_device = math.ceil(self.num_of_mic / 2)

        # 記錄所有麥克風資訊
        self.mic_list = self.createMic()

        # 紀錄當前已啟動的麥克風
        self.activated_mic_set = set()
        self.mic_thread_list = [None] # list[0] is None

        # 音檔編號
        self.record_num = 0

        # 存音檔到今天日期資料夾YYYY_MM_DD_audios/
        self.copied_audio_folder = str(time.strftime("%Y_%m_%d", time.localtime())) + "_audios/"
        self.createFolder(self.copied_audio_folder)

        # 當GUI開啟時，recognition_audio_list會初始化成list()，存放待會GUI要拿取的音檔
        self.recognition_audio_list = None

        # 自己的物件(MicrophoneRecordingThread)
        self.mic_record = None

    # 將所有音效卡執行緒的frame初始化
    def intializeRecordingThread(self):
        for mic in self.mic_record:
            mic.recording_thread.initializeFrameList()

    # 建立資料夾
    def createFolder(self, folder):
        if not os.path.exists(folder):
            os.mkdir(folder)

    # 存放自己的物件
    def storeSelfObject(self, mic_record):
        self.mic_record = mic_record

    # 記錄所有麥克風資訊
    def createMic(self):
        pa = pyaudio.PyAudio()

        mic_list = []
        # 麥克風資訊類別 class Microphone()
        # 初始化麥克風編號後存入mic_list
        for i in range(1, self.num_of_mic + 1):
            mic_object = Microphone(i, None, None)
            mic_list.append(mic_object)

        mic_device_name = ['DVS Receive  1-2 (Dante Virtual', 'DVS Receive  3-4 (Dante Virtual', 'DVS Receive  5-6 (Dante Virtual']
        mic_device_name += ['DVS Receive  7-8 (Dante Virtual', 'DVS Receive  9-10 (Dante Virtua']

        # 2支麥克風共用1個本機音訊裝置e.g.: 1號和2號使用"DVS Receive 1-2"
        # 製作音訊裝置名稱對應麥克風編號list的字典
        # {'DVS Receive  1-2 (Dante Virtual': [1, 2], 'DVS Receive  3-4 (Dante Virtual': [3, 4], ...}
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
        """            
            下面列出 device_dict = pa.get_device_info_by_index(本機音訊裝置編號) 的部分結果            
            ====== Dante虛擬音效卡 ======
            {'index': 2, 'structVersion': 2, 'name': 'DVS Receive  9-10 (Dante Virtua', 'hostApi': 0, 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultLowInputLatency': 0.09, 'defaultLowOutputLatency': 0.09, 'defaultHighInputLatency': 0.18, 'defaultHighOutputLatency': 0.18, 'defaultSampleRate': 44100.0}
            {'index': 3, 'structVersion': 2, 'name': 'DVS Receive  1-2 (Dante Virtual', 'hostApi': 0, 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultLowInputLatency': 0.09, 'defaultLowOutputLatency': 0.09, 'defaultHighInputLatency': 0.18, 'defaultHighOutputLatency': 0.18, 'defaultSampleRate': 44100.0}
            {'index': 4, 'structVersion': 2, 'name': 'DVS Receive  7-8 (Dante Virtual', 'hostApi': 0, 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultLowInputLatency': 0.09, 'defaultLowOutputLatency': 0.09, 'defaultHighInputLatency': 0.18, 'defaultHighOutputLatency': 0.18, 'defaultSampleRate': 44100.0}
            {'index': 5, 'structVersion': 2, 'name': 'DVS Receive  3-4 (Dante Virtual', 'hostApi': 0, 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultLowInputLatency': 0.09, 'defaultLowOutputLatency': 0.09, 'defaultHighInputLatency': 0.18, 'defaultHighOutputLatency': 0.18, 'defaultSampleRate': 44100.0}
            {'index': 8, 'structVersion': 2, 'name': 'DVS Receive  5-6 (Dante Virtual', 'hostApi': 0, 'maxInputChannels': 2, 'maxOutputChannels': 0, 'defaultLowInputLatency': 0.09, 'defaultLowOutputLatency': 0.09, 'defaultHighInputLatency': 0.18, 'defaultHighOutputLatency': 0.18, 'defaultSampleRate': 44100.0}
        
            'index': 本機音訊裝置編號
            'name': 音訊裝置(Dante音效卡)名稱
        """
        # 將 麥克風編號 對應到 裝置編號
        try:
            for i in range(30):
                device_dict = pa.get_device_info_by_index(i)

                if device_dict["name"] in mic_num_dev_name_dict.keys():
                    mic_num_list = mic_num_dev_name_dict[ device_dict["name"] ]
                    for mic_num in mic_num_list:
                        mic_list[mic_num-1].device_number = i

        except:
            pass
        """ 
            麥克風編號    裝置編號(index)    錄音執行緒(尚未建立)
            mic num: 1, device_number: 3, recording_thread: None
            mic num: 2, device_number: 3, recording_thread: None
            mic num: 3, device_number: 5, recording_thread: None
            mic num: 4, device_number: 5, recording_thread: None
            mic num: 5, device_number: 8, recording_thread: None
            mic num: 6, device_number: 8, recording_thread: None
            mic num: 7, device_number: 4, recording_thread: None
            mic num: 8, device_number: 4, recording_thread: None
            mic num: 9, device_number: 2, recording_thread: None
            mic num: 10, device_number: 2, recording_thread: None
        """
        # 印出所有麥克風資訊
        for mic in mic_list:
            print(f"mic num: {mic.mic_number}, device_number: {mic.device_number}, recording_thread: {mic.recording_thread}")

        return mic_list

    # 為每一個音訊裝置產生一個執行緒
    def createMicThread(self):

        try:
            ctr = 1
            for i in range(1, self.num_of_device+1):
                # 呼叫recording_thread_multi_mic.py為每張Dante音效卡建立錄音執行緒
                thread = rt.RecordingThread(self.mic_list[ctr-1].device_number, self.mic_record, self.copied_audio_folder)
                thread.setDaemon(True)
                # 呼叫RecordingThread的run()
                thread.start()
                for j in range(ctr, ctr+2):
                    if j > len(self.mic_list):
                        j = len(self.mic_list)-1

                    self.mic_list[j-1].recording_thread = thread

                ctr += 2

        except Exception as e:
            print(e)
            exit(0)

    def pressMic(self, mic_number):
        # 呼叫執行緒紀錄起始的frame index
        self.mic_list[mic_number-1].recording_thread.press_button_play(mic_number)
        self.activated_mic_set.add(mic_number)

    def shutdownMic(self, mic_number):
        # 呼叫執行緒紀錄結束的frame index來擷取一段語音frame，然後存音檔
        self.mic_list[mic_number - 1].recording_thread.press_button_stop(mic_number, self.record_num)
        self.record_num += 1

    # cocon_api.py會呼叫此函式傳送 剛啟動 的mic_number
    def get_activated_mic_number(self, activated_mic_number):

        print(f"開啟 mic {activated_mic_number}")

        mic_record.pressMic(activated_mic_number)

    # cocon_api.py會呼叫此函式傳送 剛關閉 的mic_number
    def get_inactivated_mic_number(self, inactivated_mic_number):

        print(f"關閉 mic {inactivated_mic_number}")

        mic_record.shutdownMic(inactivated_mic_number)

# 麥克風資訊類別，此類別物件會存在mic_list中
class Microphone():
    def __init__(self, mic_number, device_number, recording_thread):
        # 連接會議主機的麥克風編號，唯一編號，從1開始編
        self.mic_number = mic_number
        # 本機電腦識別的音訊裝置編號(Dante音效卡)，2支麥克風會共用1個本機音訊裝置編號
        self.device_number = device_number
        # 紀錄語音訊號的執行緒，1個本機音訊裝置編號(Dante音效卡)會使用1個執行緒
        self.recording_thread = recording_thread

# GUI會呼叫此函式取得音檔名稱
@app.route('/getAudio', methods=['POST'])
def get_audio():
    data = {}
    # 如果recognition_audio_list有音檔名稱就回傳給GUI
    if mic_record.recognition_audio_list is not None:
        if len(mic_record.recognition_audio_list) > 0:
            data["audio_file"] = mic_record.recognition_audio_list[0]
            del mic_record.recognition_audio_list[0]
            print(f"回傳 {data} 給GUI")


    return jsonify(data)

# GUI會呼叫此函式初始化要辨識的音檔清單
@app.route('/initializeRecogAudioList', methods=['POST'])
def initialize_recog_audio_list():
    mic_record.recognition_audio_list = []
    data = {"return_value": 1}
    return jsonify(data)

# recording server Main
if __name__ == '__main__':
    print("啟動Recording Server - port 4000")
    # 呼叫cocon_api.py建立擷取網路封包的執行緒
    cocon = cocon_api.CoConAPI()

    # 建立麥克風資訊
    mic_record = MicrophoneRecordingThread()
    mic_record.storeSelfObject(mic_record)
    # 建立音效卡錄音執行緒
    mic_record.createMicThread()
    # 給cocon_api.py mic_record物件，讓它能傳送"剛啟動"和"關閉"的麥克風編號
    cocon.storeMicrophoneRecordingObject(mic_record)

    app.run(threaded=False, port=4000)

