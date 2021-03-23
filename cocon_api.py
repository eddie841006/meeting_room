
"""
    cocon_api.py 由 recording_server.py 呼叫，負責擷取並解析來自會議主機的封包，如果封包含有麥克風開關的資料字串，會呼叫recording_server.py建立的執行緒錄音

    含有麥克風開關的資料字串(長度73)示意如下: 假設seat 2的麥克風開啟，"Speakers"列出所有已啟動的麥克風編號
    b'"{\\"MicrophoneState\\":{\\"Speakers\\":[2],\\"Requests\\":[],\\"Replies\\":[]}}"'

    假設seat 2的麥克風關閉，應會收到下列資訊，字串長度72
    b'"{\\"MicrophoneState\\":{\\"Speakers\\":[],\\"Requests\\":[],\\"Replies\\":[]}}"'

    含有麥克風按鈕事件的封包參考如下(此程式沒有用到下列封包)：
    b'"{\\"MicButtonEvent\\":{\\"Event\\":\\"down\\",\\"SeatNr\\":2}}"'    長度56
    b'"{\\"MicButtonEvent\\":{\\"Event\\":\\"up\\",\\"SeatNr\\":2}}"'      長度54

"""

import requests
import json
import socket
import struct
import threading
import time

# 負責錄音的server IP和port
recording_server_ip_port = "http://127.0.0.1:4000"
# 會議主機IP
plinux_server_ip = "172.16.121.130"
# 會議主機API url
plinux_server_url = "http://172.16.121.130:8890/CoCon"
# 本機電腦IP
local_ip = "172.16.121.132"


class CoConAPI():
    def __init__(self):

        # create a raw socket and bind it to the public interface
        # 建立socket，用於擷取網路封包
        self.rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)

        # Bind a interface with public IP
        # 將socket綁定至本機IP
        self.rawSocket.bind((local_ip, 0))
        print(f"[系統訊息: 建立socket擷取來自會議主機(IP {plinux_server_ip})的封包，本機的ip應為{local_ip}]")

        self.rawSocket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)  # Include IP headers
        # socket接收所有類型的封包
        self.rawSocket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)  # receive all packages

        # 與會議主機建立連線
        self.createControlConnection()

        # 當前已開啟的麥克風集合
        self.mic_set = set()
        # 上一時刻開啟的封包集合
        self.previous_mic_set = set()
        # previous_mic_set 和 mic_set作差集就能得出"剛剛關閉"的麥克風編號

        # 啟動擷取網路封包的執行緒
        self.packet_sniffing_thread = threading.Thread(target=self.packetSniffer)
        self.packet_sniffing_thread.setDaemon(False)
        self.packet_sniffing_thread.start()

    # 儲存 recording_server.py 的 MicrophoneRecordingThread 物件
    def storeMicrophoneRecordingObject(self, mic_record):
        self.mic_record = mic_record

    # 與會議主機建立連線
    def createControlConnection(self):

        self.conn_resquest = requests.get('http://172.16.121.130:8890/CoCon/Connect')

        self.conn_resp = json.loads(json.loads(self.conn_resquest.text))

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

    # 這個函式目前沒有用到
    # disableMic會關閉activated_mic_set裡所有的麥克風
    def disableMic(self, activated_mic_set):
        print("[系統訊息: 關閉所有已啟動的麥克風]")
        for i in activated_mic_set:
            self.conn_resquest = requests.get(plinux_server_url + '/Microphone/SetState/?State=Off&SeatNr='+str(i))

    def closeSocket(self):
        self.rawSocket.close()

    # 過濾資料長度，感興趣的是下列封包資料(字串長度是72)，10支麥克風都開啟的話，字串長度是
    # b'"{\\"MicrophoneState\\":{\\"Speakers\\":[],\\"Requests\\":[],\\"Replies\\":[]}}"'
    def filterWithDataLength(self, length):
        if length>70 and length<=100:
            return True
        return False

    # 解析來自會議主機的封包，取得資料字串
    # 擷取的資料字串是 b'"{\\"MicrophoneState\\":{\\"Speakers\\":[],\\"Requests\\":[],\\"Replies\\":[]}}"'
    def parsePacket(self, packet):

        ip_length = 20
        ip = struct.unpack("!BBHHHBBH4s4s", packet[0:ip_length])
        IHL = (ip[0] & 0xf) * 4
        source_ip = socket.inet_ntoa(ip[8])

        mic_msg = None

        # 如果封包紀錄的來源IP是會議主機IP才繼續處理
        if source_ip == plinux_server_ip:

            # 攜帶麥克風資訊的封包是使用TCP協定，TCP協定在IP封包中紀錄的編號是6
            if ip[6] == 6:
                # TCP = 0x06
                tcp_packet = packet[IHL:]
                tcp_length = 20
                tcp = struct.unpack("!HHLLBBHHH", tcp_packet[0:tcp_length])

                tcp_length = (tcp[4] >> 4) * 4
                # 取得TCP協定攜帶的資料長度
                tcp_data_len = len(tcp_packet[tcp_length:])

                # 透過資料長度過濾封包
                if self.filterWithDataLength(tcp_data_len):
                    try:
                        # 資料解碼
                        mic_msg = tcp_packet[tcp_length:].decode("UTF-8")

                    except Exception as e:
                        pass

        return mic_msg

    # 從資料字串擷取出"剛開啟"和"剛關閉"的麥克風編號
    def getSpeaker(self, mic_msg):
        if mic_msg is not None:
            # 將資料字串轉換成字典型態
            # {"MicrophoneState":{"Speakers":[],"Requests":[],"Replies":[]}}
            mic_msg_dict = eval(json.loads(mic_msg))

            # 如果字典key含有"MicrophoneState"才繼續處理
            if "MicrophoneState" in mic_msg_dict:
                print("=== previous_mic_set ===")
                print(self.previous_mic_set)

                # 取出Speakers清單
                mic_number_list = mic_msg_dict["MicrophoneState"]["Speakers"]
                list_len = len(mic_number_list)
                print(f"麥克風: {mic_number_list}")
                # 如果目前有麥克風已啟動
                if list_len > 0:

                    for mic_number in mic_number_list:

                        if mic_number not in self.mic_set:
                            # 將已開啟的麥克風編號存入集合
                            self.mic_set.add(mic_number)

                            print("=== mic_set add ===")
                            print(self.mic_set)

                            # 如果麥克風不在上一時刻的集合出現，代表該麥克風是剛剛才啟動，
                            # 這時要呼叫reocrding_server.py的錄音執行緒錄音
                            if mic_number not in self.previous_mic_set:
                                print(f"getSpeaker act {mic_number}")
                                self.mic_record.get_activated_mic_number(mic_number)

                # 取得剛關閉的麥克風集合
                diff_mic_set = self.previous_mic_set - self.mic_set

                if len(diff_mic_set) > 0:
                    # 每個剛關閉的麥克風都停止錄音
                    # 呼叫reocrding_server.py的錄音執行緒擷取錄製的語音段
                    for mic_number in diff_mic_set:
                        print(f"getSpeaker inact {mic_number}")
                        self.mic_record.get_inactivated_mic_number(mic_number)

                self.previous_mic_set = self.mic_set.copy()
                self.mic_set.clear()

    # 擷取網路封包
    def packetSniffer(self):
        s = time.time()
        while True:
            try:
                # 擷取封包至buffer
                packet = self.rawSocket.recvfrom(9192)[0]
                # 解析封包，取得資料字串
                mic_msg = self.parsePacket(packet)
                # 從資料字串擷取出開啟或關閉的麥克風編號
                self.getSpeaker(mic_msg)
            except Exception as e:
                pass

            # 每分鐘和會議主機重新建立連線
            t = time.time()
            if t-s >= 60:
                self.createControlConnection()
                s = time.time()

if __name__ == '__main__':
    cocon = CoConAPI()

