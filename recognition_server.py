
"""

    recognition_server.py是獨立的flask API server，功能如下:
    1. 等待GUI呼叫/postAudioFile，將音檔資料傳送製後端AI server(ip 172.16.121.124)
    2. 將AI server回傳的辨識結果再傳給GUI

"""

from flask import Flask, jsonify, request
import glob
import numpy as np
import wave
import os
import shutil
import requests
import json
import re

import BIC.speech_segmentation as bic_seg

app = Flask(__name__)
app.config["DEBUG"] = True

class Process():
    def __init__(self):
        pass

    def cut_wave(self, wav, sr, save_file):
        frame_size = 256
        frame_shift = 128

        seg_point = bic_seg.multi_segmentation(np.array(wav), sr, frame_size, frame_shift, save_file, plot_seg=False,
                                               save_seg=True,
                                               cluster_method='bic')
        print('The segmentation point for this audio file is listed (Unit: /s)', seg_point)

    # 取得語者辨識結果
    def speaker_id(self, wav):
        url = "http://172.16.121.124:6001/speaker"
        text = {"speaker": wav}
        a = requests.post(url, json=text)
        speaker = json.loads(a.text)["name"]

        print("server: "+speaker)
        return speaker

    # 取得語音辨識結果
    def speech_MASR(self, wave_path):
        print(f"==========\nIn server speech_MASR\n{wave_path}")

        with wave.open(wave_path) as wav:
            wav = np.frombuffer(wav.readframes(wav.getnframes()), dtype="int16")
            wav = wav.astype("float")
        wav = (wav - wav.mean()) / wav.std()

        url = "http://172.16.121.124:6002/MASR"
        waves = {"speech": wav.tolist()}  # spectrum頻譜
        rt = requests.post(url, json=waves)  # 將list資料post至指定url的flask
        text = rt.text  # rt回傳資料

        return text

    # 取得摘要生成結果
    def run_summary(self, content):
        print(f"==========\nIn server run_summary\n{content}")

        if len(content) > 1:
            content = "，".join(content)
        elif len(content) == 0:
            content = "無法辨識"
        else:
            content = content[0]
        content = re.sub(r'無法辨識，|，無法辨識$', '', content)
        url = "http://172.16.121.124:6000/summarization"
        ttext = {"text": content}
        # print("summary ttext1:", ttext)
        s = requests.post(url, json=ttext)
        summary = s.text[:]

        if len(content) <= 25:
            summary = str(content)
        else:
            if summary == '':
                for ii in range(10):
                    if summary == '':
                        s = requests.post(url, json=ttext)
                        summary = s.text[:-1]
                        print(ii)
                if summary == '':
                    summary = "無法進行摘要辨識"

        search_meeting_annouce = re.search(r'會議(議|一)程.*主席.*投資.*討論.*共\d+分鐘', content)
        search_meeting_duration = re.search(r'共\d+分鐘', content)
        if search_meeting_annouce:  # 1081219
            summary = "會議議程" + search_meeting_duration.group()

        return summary



# GUI呼叫此函式傳送音檔資料
@app.route('/postAudioFile', methods=['POST'])
def post_audio_file():
    data = request.get_json()
    # 語音frame
    wav = data["wav"]
    # 取樣率
    sr = data["sr"]

    data = {}

    # 語者辨識
    data["speaker"] = process.speaker_id(wav)

    # 語音辨識
    save_file = "save_audio/"

    process.cut_wave(wav, sr, save_file)
    c_wav = sorted(glob.glob(os.path.join(save_file, '*.wav')))
    speech_results = []

    speech_text = ""
    for wav_cnam in c_wav:
        speech = process.speech_MASR(wav_cnam)
        if speech != "":
            speech_results.append(speech)
            speech_text += speech

    shutil.rmtree(save_file)

    data["speech"] = speech_results

    # 摘要
    summary = process.run_summary(speech_results)

    data["summary"] = summary

    # 回傳辨識結果給GUI
    return jsonify(data)

if __name__ == '__main__':
    process = Process()
    print("啟動Recognition Server - port 3000")
    app.run(threaded=False, port=3000)