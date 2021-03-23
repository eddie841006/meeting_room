from flask import Flask, jsonify, request
import requests
import json
import sys
import os
import re
import binascii
import socket
import struct
import threading
import pyaudio as pyaudio
import time
import math
import recording_thread_multi_mic as rt

app = Flask(__name__)
app.config["DEBUG"] = True

class PacketSnifferThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        self.mic_record = None
        # create a raw socket and bind it to the public interface
        self.rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)

        # Bind a interface with public IP
        cocon_server_ip = "172.16.121.132"
        self.rawSocket.bind((cocon_server_ip, 0))
        print(f"[系統訊息: 建立socket擷取來自會議主機的封包，本機的ip應為{cocon_server_ip}]")

        self.rawSocket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)  # Include IP headers
        self.rawSocket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)  # receive all packages


        self.createControlConnection()

        self.mic_set = set()
        self.previous_mic_set = set()

        self.mic_dict = {}

        # self.packet_sniffing_thread = threading.Thread(target=self.packetSniffer)
        # self.packet_sniffing_thread.setDaemon(True)  # 守護執行緒
        # self.packet_sniffing_thread.start()



    def storeMicrophoneRecordingObject(self, mic_record):
        self.mic_record = mic_record

    def createControlConnection(self):

        self.conn_resquest = requests.get('http://172.16.121.130:8890/CoCon/Connect')
        print("self.conn_resquest.text: ", self.conn_resquest.text)

        self.conn_resp = json.loads(json.loads(self.conn_resquest.text))

        # self.conn_resp = self.conn_resquest.json()

        print("conn resp: ", self.conn_resp)
        print("conn resp type: ", type(self.conn_resp))

        # self.conn_resp = json.loads(self.conn_resquest.json())
        # self.conn_resp = json.loads(self.conn_resquest)

        self.connect_bool = self.conn_resp['Connect']
        self.noti_id = self.conn_resp['id']

        # True代表成功取得ID
        if self.connect_bool:
            print("[系統訊息: 成功獲取會議主機的連線ID，能夠接收來自會議主機傳過來的麥克風訊號]")
            print(self.connect_bool)
            print(self.noti_id)
        else:
            print("[系統訊息: 無法取得會議主機的連線ID，請確認網路連線後再重試]")
            exit(0)

    def disableMic(self, activated_mic_set):
        print("[系統訊息: 關閉所有已啟動的麥克風]")
        for i in activated_mic_set:
            self.conn_resquest = requests.get('http://localhost:8890/CoCon/Microphone/SetState/?State=Off&SeatNr='+str(i))

    def closeSocket(self):
        self.rawSocket.close()

    def filterWithDataLength(self, length):
        if (length>70 and length<80) or (length>=54 and length <=58):
            return True
        return False

    def parsePacket(self, packet):
        # print(f"parse packet")
        ip_length = 20
        ip = struct.unpack("!BBHHHBBH4s4s", packet[0:ip_length])
        IHL = (ip[0] & 0xf) * 4
        source_ip = socket.inet_ntoa(ip[8])

        mic_msg = None
        # print(source_ip)
        # print(packet)
        if source_ip == "172.16.121.130":
            # print(source_ip)
            if ip[6] == 6:
                # TCP = 0x06
                tcp_packet = packet[IHL:]
                tcp_length = 20
                tcp = struct.unpack("!HHLLBBHHH", tcp_packet[0:tcp_length])

                # Real tcp header length
                tcp_length = (tcp[4] >> 4) * 4
                tcp_data_len = len(tcp_packet[tcp_length:])
                if self.filterWithDataLength(tcp_data_len):
                    # mic_msg = str(tcp_packet[tcp_length:])
                    try:
                        mic_msg = tcp_packet[tcp_length:].decode("UTF-8")
                        # mic_msg = tcp_packet[tcp_length:]
                        # print("=== mic_msg ===")
                        # print(mic_msg)
                    except:
                        pass
                    # print("Raw byte data: ", tcp_packet[tcp_length:])
                    # print("TCP data length: ", tcp_data_len)

        return mic_msg


    def getSpeaker(self, mic_msg):
        if mic_msg is not None:

            mic_msg_dict = eval(json.loads(mic_msg))

            # print("=== mic msg dict ===")
            # print(mic_msg_dict)
            # print(type(mic_msg_dict))

            if "MicrophoneState" in mic_msg_dict:

                mic_number_list = mic_msg_dict["MicrophoneState"]["Speakers"]
                list_len = len(mic_number_list)
                print(f"麥克風: {mic_number_list}")
                # 如果目前有麥克風已啟動
                if list_len > 0:

                    for mic_number in mic_number_list:
                        # 取出所有
                        if mic_number not in self.mic_set:
                            self.mic_set.add(mic_number)
                            self.mic_dict[str(mic_number)] = 1
                            # print("=== mic_set add ===")
                            # print(self.mic_set)
                            # print('='*20)
                            #
                            if mic_number not in self.previous_mic_set:
                                self.mic_record.pressMic(mic_number)
                                # self.createControlConnectinon()
                                # self.gui.press_button_play(mic_number)

                # check whether the mic stop receiving voice
                diff_mic_set = self.previous_mic_set - self.mic_set
                # print("=== diff_mic_set ===")
                # print(diff_mic_set)
                # print('='*20)
                if len(diff_mic_set) > 0:
                    for mic_number in diff_mic_set:
                        self.mic_dict[str(mic_number)] = 0
                        # self.mic_set.remove(mic)
                        # mic stopped receiving voice

                        # self.gui.press_button_stop(mic_number)

                        # dependence
                        self.mic_record.shutdownMic(mic_number)
                        # self.createControlConnectinon()

                self.previous_mic_set = self.mic_set.copy()
                self.mic_set.clear()

        # The return number has no meaning
        return 1

    def run(self):
        s = time.time()
        num = 0
        while True:
            num += 1
            print("get packet", num)
            try:
                packet = self.rawSocket.recvfrom(9192)[0]
            except:
                pass
            mic_msg = self.parsePacket(packet)
            new_speaker = self.getSpeaker(mic_msg)

            t = time.time()
            if t-s >= 60:
                self.createControlConnection()
                s = time.time()

###
###
###
class MicrophoneRecordingThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
# class MicrophoneRecording():
#     def __init__(self):
        self.num_of_mic = 10  #
        # 2支麥克風共用1個本機音訊裝置e.g.: 1號和2號使用"DVS Receive 1-2"
        self.num_of_device = math.ceil(self.num_of_mic / 2)

        # 記錄所有麥克風資訊，mic_dict {"device_index": 音源裝置(麥克風)系統編號, "thread": 紀錄音訊串流(麥克風聲音)以及處理切音的執行緒}
        self.mic_list = self.createMic()
        self.createMicThread()

        self.cocon = None

        # 紀錄當前已啟動的麥克風
        self.activated_mic_set = set()
        self.mic_thread_list = [None] # list[0] is None

        # 此資料夾暫存會議進行過程所錄製的音檔
        self.tmp_audio_folder = "all_records/"
        if not os.path.exists(self.tmp_audio_folder):
            os.mkdir(self.tmp_audio_folder)

        self.record_num = 0

        # 收集recording_thread錄製的音檔
        self.recording_audio_list = []
        self.recording_audio_ctr = 0


    def createMic(self):
        pa = pyaudio.PyAudio()
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
                device_dict = pa.get_device_info_by_index(i)

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

    # def storeSelfGUIObject(self, gui):
    #     self.gui = gui
    #
    # def storeCoconObject(self, cocon):
    #     self.cocon = cocon
    #
    # # reset connection manually
    # def resetConnection(self):
    #     self.cocon.createControlConnection()
    #     self.cocon.disableMic(self.activated_mic_set)

    def createMicThread(self):

        try:
            # 為每一個音訊裝置產生一個執行緒
            ctr = 1
            for i in range(1, self.num_of_device+1):
                # mic_number, mic_device_index, gui
                thread = rt.RecordingThread(self.mic_list[ctr-1].device_number, None)
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

        self.mic_list[mic_number-1].recording_thread.press_button_play(mic_number)
        self.activated_mic_set.add(mic_number)

    def shutdownMic(self, mic_number):
        # self.swith_button_status('stop')
        # self.activated_mic_set.remove(mic_number)
        self.mic_list[mic_number - 1].recording_thread.press_button_stop(mic_number, self.record_num)
        self.record_num += 1

class Microphone():
    def __init__(self, mic_number, device_number, recording_thread):
        # 連接會議主機的麥克風編號，唯一編號，從1開始編
        self.mic_number = mic_number
        # 本機電腦識別的音訊裝置編號，2支麥克風會共用1個本機音訊裝置編號
        self.device_number = device_number
        # 紀錄語音訊號的執行緒，1個本機音訊裝置編號(2支麥克風)會使用1個執行緒
        self.recording_thread = recording_thread

# def main():
#     cocon = CoConAPI(None)
#     # # create a raw socket and bind it to the public interface
#     # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
#     #
#     # # Bind a interface with public IP
#     # rawSocket.bind(("192.168.0.104", 0))
#     #
#     # rawSocket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)  # Include IP headers
#     # rawSocket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)  # receive all packages
#     # print("Socket is created successfully!")
#     #
#     # conn_resquest = requests.get('http://localhost:8890/CoCon/Connect')
#     # conn_resp = json.loads(conn_resquest.json())
#     # print(conn_resp['Connect'])
#     # print(conn_resp['id'])
#
#     # unsubscribe_delegate_request = requests.get('http://localhost:8890/CoCon/Unsubscribe/?Model=Delegate&id='+conn_resp['id'])
#
#
#     # b'"{\\"MicButtonEvent\\":{\\"Event\\":\\"up\\",\\"SeatNr\\":2}}"', 54
#     # b'"{\\"MicButtonEvent\\":{\\"Event\\":\\"down\\",\\"SeatNr\\":2}}"', 56
#     # b'"{\\"MicrophoneState\\":{\\"Speakers\\":[2],\\"Requests\\":[],\\"Replies\\":[]}}"', 73
#     # b'"{\\"MicrophoneState\\":{\\"Speakers\\":[],\\"Requests\\":[],\\"Replies\\":[]}}"', 72
#
#     while True:
#         packet = cocon.rawSocket.recvfrom(9192)[0]
#         mic_msg = cocon.parsePacket(packet)
#         new_speaker = cocon.getSpeaker(mic_msg)
#
#     cocon.closeSocket()


# recording_thread會呼叫此函式儲存音檔
@app.route('/appendAudio', methods=['POST'])
def append_audio():
    print(f"==========\n append_audio")

    data = request.get_json()
    audio_name = json.loads(data.text)["audio_name"]
    mic_record.recording_audio_list.append(audio_name)

    return ""

# GUI會呼叫此函式取得音檔名稱
@app.route('/getAudio', methods=['POST'])
def get_audio():
    print(f"==========\n get_audio")
    data = request.get_json()
    audio_ctr = json.loads(data.text)["audio_ctr"]

    data = {}
    if audio_ctr < len(mic_record.recording_audio_list):
        data["audio_file"] = mic_record.recording_audio_list[audio_ctr]

    return jsonify(data)


is_server_starting = False
if __name__ == '__main__':

    if not is_server_starting:
        print("server已啟動")

        packet_sniffing_thread = PacketSnifferThread()
        # packet_sniffing_thread.storeMicrophoneRecordingObject(mic_record)

        packet_sniffing_thread.setDaemon(False)  # 守護執行緒True
        packet_sniffing_thread.start()


        mic_record = MicrophoneRecordingThread()

        # cocon = CoConAPI(None)


        is_server_starting = True

    # app.run(threaded=False, port=3000)