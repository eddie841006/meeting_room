
"""

    meeting_record.py 由 GUI 呼叫，負責儲存會議記錄至資料夾 YYYY_MM_DD_meeting/，檔案說明如下:
    1. 語者逐字稿檔 YYYY-MM-DD_HH-mm-ss_會議逐字稿.txt
    2. 語者摘要檔 YYYY-MM-DD_HH-mm-ss_會議紀錄摘要.txt
    3. 會議完整語音檔 YYYY-MM-DD_HH-mm-ss_record_original.wav
    4. 語音時間標記檔 YYYY-MM-DD_HH-mm-ss_record_original.txt

"""

import os
import time
import wave

class MeetingRecord():
    def __init__(self):

        # 語者和語音辨識結果字串
        self.save_txt = ""
        # 語者和摘要結果字串
        self.save_sum = ""

        # 會議的speaker列表
        self.label_speaker_list = []
        # 會議語音辨識內容列表
        self.label_asr_list = []
        # 會議摘要內容列表
        self.label_summary_list = []

        # 會議記錄將儲存於YYYY_mm_dd_meeting/資料夾下
        self.date_folder_name = str(time.strftime("%Y_%m_%d", time.localtime())) + "_meeting"
        # 會議開始時間，存音檔和會議記錄都用時間開頭命名
        self.meeting_time = str(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()))

        # 產生檔名
        self.createRecordFileName()

    def createRecordFileName(self):

        if not os.path.isdir(self.date_folder_name):
            os.mkdir(self.date_folder_name)

        self.record_folder = self.date_folder_name

        # 會議語音檔名
        self.save_wave_name = self.record_folder  + "/" + self.meeting_time + "_record_original.wav"
        # 語音檔時間標記檔名
        self.save_label_name = self.record_folder  + "/" + self.meeting_time + "_record_original.txt"

    def saveMasrResult(self, speaker, masr_result):
        self.save_txt += speaker + "\t" + masr_result + "\n"
        self.label_speaker_list.append(speaker)
        self.label_asr_list.append(masr_result)

    def saveSummary(self, speaker, summary):
        self.save_sum += speaker + "\t" + summary + "\n"
        self.label_summary_list.append(summary)

    # GUI關閉時，呼叫此函式初始化會議紀錄
    def clearRecord(self):
        self.save_txt = ""
        self.save_sum = ""
        self.label_speaker_list = []
        self.label_asr_list = []

    # 由GUI呼叫此函式，此函式傳入音檔名稱list，串接音檔並製作時間標記檔
    # 3. 會議完整語音檔 YYYY-MM-DD_HH-mm-ss_record_original.wav
    # 4. 語音時間標記檔 YYYY-MM-DD_HH-mm-ss_record_original.txt
    def concatenateRecordFile(self, meeting_record_audio_list):

        f1 = open(self.save_label_name, 'w', encoding='utf-8')

        audio_previous_time = 0.0

        if len(meeting_record_audio_list) > 0:
            print("串接錄製的音檔 ...")

            # 製作音檔時間點對應語者和語音逐字稿的label檔
            if len(meeting_record_audio_list) == len(self.label_speaker_list) == len(self.label_asr_list):

                data = []
                for f,speaker,asr in zip(meeting_record_audio_list, self.label_speaker_list, self.label_asr_list):
                    w = wave.open(f, 'rb')
                    # 音檔長度
                    audio_duration = w.getnframes() / w.getframerate()

                    audio_duration += audio_previous_time

                    record_label_line = str(audio_previous_time) + "," + str(audio_duration) + "," + speaker + "," + asr + "\n"

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

                print("語者和語音逐字稿的label檔寫入完成\n音檔串接完成")

            else:
                print("[系統訊息: 辨識過程或暫存音檔有遺失資料，meeting_record_audio_list的音檔數、語者列表長度以及語音逐字稿列表長度不符]")
                print("meeting_record_audio_list的音檔數:", len(meeting_record_audio_list))
                print("語者列表長度:", len(self.label_speaker_list))
                print("語音逐字稿列表長度:", len(self.label_asr_list))

                data = []
                for f in meeting_record_audio_list:
                    w = wave.open(f, 'rb')
                    data.append([w.getparams(), w.readframes(w.getnframes())])

                output = wave.open(self.save_wave_name, 'wb')
                output.setparams(data[0][0])

                for i in range(len(data)):
                    output.writeframes(data[i][1])

                output.close()  # close audio file
                print("只串接音檔")

        else:
            print("沒有音檔")

    # 會議紀錄寫檔
    # 1. 語者逐字稿檔 YYYY-MM-DD_HH-mm-ss_會議逐字稿.txt
    # 2. 語者摘要檔 YYYY-MM-DD_HH-mm-ss_會議紀錄摘要.txt
    def writeMeetingRecord(self):

        if self.save_txt != '':
            print("寫入會議記錄 ...")
            save_txt_name = self.record_folder + "/" + self.meeting_time + '_會議逐字稿' +'.txt'
            f2 = open(save_txt_name, 'w', encoding='utf-8')
            f2.write(self.save_txt)
            f2.close()

            if self.save_sum != '':
                save_sum_name = self.record_folder + "/" + self.meeting_time + '_會議紀錄摘要' +'.txt'
                f3 = open(save_sum_name, 'w', encoding='utf-8')
                f3.write(self.save_sum)
                f3.close()
        else:
            print("沒有會議記錄")

