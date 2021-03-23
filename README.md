# meeting_room

智慧型會議室系統讓使用者能透過麥克風發言，然後系統再將發言者、發言內容和發言摘要呈現在圖形介面上，要達到上述功能必須要有程式進行設備間的介接，協助傳遞資料。本文件要來說明進行介接的Python程式，程式的主要功能簡述如下：
* 能各別錄製會議主機麥克風的語音串流。
* 能讀到特定麥克風的按鈕事件，進而觸發程式切割語音片段後送AI伺服器進行語音辨識，最後將辨識結果呈現在圖形介面上。

## 一、系統概觀與程式流程

圖1呈現系統概觀，系統包含3個主機（黃色方塊）：會議主機、本機電腦與AI伺服器，主機之間透過有線網路（綠色實心箭頭）通訊，介接程式為圖中3個藍色方塊，分別是Recording server、GUI和Recognition server，實作在本機電腦。當有麥克風開啟與關閉事件發生時，資料傳遞的流程說明如下：

1. 會議主機將麥克風開啟和關閉的訊息傳遞給Recording server，接著Recording server切割開啟到關閉時間段的語音訊號，然後儲存成一個音檔
2. GUI定期向Recording server要求新的音檔
3. Recording server回傳音檔給GUI
4. GUI將音檔的語音訊號傳遞給Recognition server
5. Recognition server將語音訊號傳給AI伺服器進行辨識語者、語音和摘要辨識
6. AI伺服器將辨識結果回傳給Recognition server
7. Recognition server將辨識結果回傳給GUI呈現在介面上

> Recognition server也可以實作在AI伺服器，上述流程不會改變

![](https://i.imgur.com/WCCvTh1.png)

圖1：系統概觀

## 二、程式說明

本節說明Recording server、Recognition server和GUI關鍵程式片段。實作的程式檔和相對應的功能說明如下：

* Recording server
    * `recording_server.py`：flask API server
        * 呼叫`recording_thread_multi_mic.py`為每張Dante虛擬音效卡建立**錄音執行緒**
        * 呼叫`cocon_api.py`建立**擷取網路封包**的執行緒
        * 回傳GUI一筆音檔名稱
        
    * `recording_thread_multi_mic.py`：監聽特定音效卡的語音訊號，將擷取的語音訊號存成音檔
    
    * `cocon_api.py`
        * 建立擷取網路封包的執行緒，並且解析封包中含有麥克風開關的訊息
        * 解析出開啟和關閉的**麥克風編號**後，經由`recording_server.py`通知`recording_thread_multi_mic.py`擷取語音訊號

* Recognition server
    * `recognition_server.py`：flask API server
        * 將GUI送來的語音訊號傳給AI伺服器等待辨識
        * 將AI伺服器回傳的辨識結果再傳給GUI
        
* GUI
    * `GUI_product_v2.py`：圖形介面程式
        * 定期向`recording_server.py`要求一個語音檔名，如果要到語音檔名，就讀取語音檔並傳送語音訊號給Recognition server等待辨識
        * 收到辨識結果後，將之呈現在圖形介面上
        * 當`GUI_product_v2.py`要關閉時，呼叫`meeting_record.py`儲存會議記錄
    
    * `meeting_record.py`：儲存會議記錄，包含串接音檔和製作語音逐字稿

### (一) Recording server

本小節說明Recording server的關鍵程式片段，Recording server除了負責擷取並解析網路封包，還有音效卡錄音功能。目前系統使用10支麥克風和5張Dante音效卡，2支麥克風共用一張音效卡傳輸語音訊號，每張音效卡是雙聲道，1支麥克風用一個聲道（channel）。每張音效卡都有名稱和裝置編號，在錄音功能實作中，需要裝置編號來讓`PyAudio`函式庫監聽特定的音效卡，裝置編號是由`PyAudio`讀取本機電腦的音效裝置而生成，而且可能因開關機等因素而變動，因此每次啟動`recording_server.py`都需要將**麥克風編號對應到裝置編號**後才能擷取到正確的訊號。
        
#### 1. `recording_server.py`
 
`recording_server.py`是flask API server，下列說明`recording_server.py`重要的程式片段

(1) 主程序

`main`程式碼
```python
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
    # port 4000
    app.run(threaded=False, port=4000)
```
 
(2) 定義儲存麥克風資訊的資料結構

定義`Microphone`類別
```python
class Microphone():
    def __init__(self, mic_number, device_number, recording_thread):
        # 連接會議主機的麥克風編號，唯一編號，從1開始編
        self.mic_number = mic_number
        # 本機電腦識別的音訊裝置編號(Dante音效卡)，2支麥克風會共用1個本機音訊裝置編號
        self.device_number = device_number
        # 語音訊號的執行緒，1個本機音訊裝置編號(Dante音效卡)會使用1個執行緒
        self.recording_thread = recording_thread
```

(3) 初始化麥克風資訊以及對應裝置編號

`createMic`函式建立`Microphone`物件並存入`list()`，先給予每支麥克風的編號
```python
    mic_list = []
    for i in range(1, self.num_of_mic + 1):
        mic_object = Microphone(i, None, None)
        mic_list.append(mic_object)
```
將麥克風編號對應到裝置編號(index)。對應是透過`PyAudio`函式庫的`get_device_info_by_index()`函式比對查找而得，從已知的裝置名稱(name)和麥克風編號對應至裝置編號
```python
    # 2支麥克風共用1個本機音訊裝置e.g.: 1號和2號使用"DVS Receive 1-2 ..."
    # mic_num_dev_name_dict = {'DVS Receive  1-2 (Dante Virtual': [1, 2], 'DVS Receive  3-4 (Dante Virtual': [3, 4], ...}
    
    for i in range(30): # 也可以這樣寫 for i in range(pa.get_device_count()) ，get_device_count()回傳音訊裝置的數量
        device_dict = pa.get_device_info_by_index(i)

        if device_dict["name"] in mic_num_dev_name_dict.keys():
            # 範例
            # mic_num_list = [1, 2]
            # device_dict["name"] = 'DVS Receive  1-2 (Dante Virtual'
            mic_num_list = mic_num_dev_name_dict[ device_dict["name"] ]
            for mic_num in mic_num_list:
                mic_list[mic_num-1].device_number = i
```
對應結果參考如下：

| 麥克風編號 | 裝置名稱(name)                  | 裝置編號(index) |
| ---------- | ------------------------------- | --------------- |
| 1, 2       | DVS Receive  1-2 (Dante Virtual | 3               |
| 3, 4       | DVS Receive  3-4 (Dante Virtual | 5               |
| 5, 6       | DVS Receive  5-6 (Dante Virtual | 8               |
| 7, 8       | DVS Receive  7-8 (Dante Virtual | 4               |
| 9, 10      | DVS Receive  9-10 (Dante Virtua | 2               |

(4) 建立錄音執行緒

`createMicThread`函式呼叫`recording_thread_multi_mic.py`（`rt.RecordingThread`），為每張音效卡裝置建立一個錄音執行緒，將執行緒各別存入`mic_list`裡頭的`Microphone`物件
```python
ctr = 1
for i in range(1, self.num_of_device+1):
    # 呼叫recording_thread_multi_mic.py為每張Dante音效卡建立錄音執行緒
    thread = rt.RecordingThread(self.mic_list[ctr-1].device_number, self.mic_record, self.copied_audio_folder)
    # 設為背景執行
    thread.setDaemon(True)
    # 呼叫RecordingThread的run()
    thread.start()
    for j in range(ctr, ctr+2):
        if j > len(self.mic_list):
            j = len(self.mic_list)-1
        # 執行緒各別存入mic_list裡頭的Microphone物件
        self.mic_list[j-1].recording_thread = thread

    ctr += 2
```

經過`createMic`和`createMicThread`的處理，`mic_list`儲存的結構如下，每列都是1個`Microphone`物件

| 麥克風編號（mic_number） | 裝置編號(device_number)  | 執行緒（recording_thread ）         |
| --------------------- | --------------------------- | ------------------------------- |
| 1                     | 3                           | RecordingThread物件0 |
| 2                     | 3                           | RecordingThread物件0 |
| 3                     | 5                           | RecordingThread物件1 |
| 4                     | 5                           | RecordingThread物件1 |
| 5                     | 8                           | RecordingThread物件2 |
| 6                     | 8                           | RecordingThread物件2 |
| 7                     | 4                           | RecordingThread物件3 |
| 8                     | 4                           | RecordingThread物件3 |
| 9                     | 2                           | RecordingThread物件4 |
| 10                    | 2                           | RecordingThread物件4 |

(5) API

API `/initializeRecogAudioList`提供GUI呼叫，用於初始化要辨識的音檔清單`recognition_audio_list`
```python
@app.route('/initializeRecogAudioList', methods=['POST'])
def initialize_recog_audio_list():
    mic_record.recognition_audio_list = []
    data = {"return_value": 1}
    return jsonify(data)
```
API `/getAudio`提供GUI呼叫，用於取得音檔名稱
```python
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
```

#### 2. `recording_thread_multi_mic.py`

`recording_thread_multi_mic.py`定義錄音的執行緒，錄製特定音效卡的語音訊號，並將擷取的語音訊號存成音檔，下列說明`recording_thread_multi_mic.py`重要的程式片段。

(1) 變數初始化

`RecordingThread(threading.Thread)`類別重要的變數
```python
# 要監聽的音效卡裝置編號
self.mic_device_index
# 單次要從音效卡抓取的frame大小
self.recording_chunk = 2048
# 取樣率
self.recording_sample_rate = 16000
# 設定錄音用的頻道數
self.recording_channel = 2
# 存放各聲道錄製的語音frame
self.frames = [[], []]
# 存放各聲道的起始語音frame index
self.start_index = [[], []]
# 存放各聲道的結束語音frame index
self.stop_index = [[], []]
```

(2) 錄音功能

`recording_server.py`的`createMicThread`函式呼叫`thread.start()`時，會執行`RecordingThread(threading.Thread)`的`run`函式，不斷擷取音效卡的訊號frame

```python
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
        # 每間隔2取frame資料存入各別的frame list
        channel0 = indata[0::2].tobytes() # 左聲道，奇數編號的麥克風訊號1, 3, 5, 7, 9
        channel1 = indata[1::2].tobytes() # 右聲道，偶數編號的麥克風訊號2, 4, 6, 8, 10
        self.frames[0].append(channel0)
        self.frames[1].append(channel1)
```

(3) 擷取訊號與存音檔功能

當開啟麥克風時，`press_button_play`函式會被呼叫，將當前的frame index存入`self.start_index list()`

```python
def press_button_play(self, mic_number):
    # 根據麥克風編號判斷左右聲道，奇數是0、偶數是1
    spec_channel = self.determineChannelNumber(mic_number, True)
    ...
    # 紀錄當前的frame index
    self.start_index[spec_channel].append(len(self.frames[spec_channel]))
```

當關閉麥克風時，`press_button_stop`函式會被呼叫，將當前的frame index存入`self.stop_index list()`，接著擷取從`start_index`到`stop_index`的語音訊號，然後存音檔至資料夾`YYYY_MM_DD_audios/`
```python
    def press_button_stop(self, mic_number, record_num):
        spec_channel = self.determineChannelNumber(mic_number, False)      
        ...
        self.stop_index[spec_channel].append(len(self.frames[spec_channel]))

        # 擷取語音訊號frame
        single_frame = self.frames[spec_channel][ self.start_index[spec_channel][ self.thread_record_num[spec_channel] ]:self.stop_index[spec_channel][ self.thread_record_num[spec_channel] ] ]
        # 將該頻道儲存的語音frame初始化為空list，避免記憶體容量不足
        self.frames[spec_channel] = []
        sub_wave_name = self.copied_audio_folder + str(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())) + "_" + str(record_num) + ".wav"

        # 存音檔
        self.save_wav(sub_wave_name, single_frame)
        # 讀音檔
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

            # GUI剛開啟的時候，recording_sever.py會將recognition_audio_list初始化為空list            
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
```

#### 3. `cocon_api.py`

`cocon_api.py`負責擷取並解析來自會議主機的網路封包，如果封包含有麥克風開關的資料字串，會呼叫`recording_server.py`建立的錄音執行緒擷取語音訊號，下列說明`cocon_api.py`重要的程式片段

(1) 建立連線

`createControlConnection`函式與會議主機建立連線，將用來取得麥克風資訊
```python
# 呼叫會議主機API建立控制連線
self.conn_resquest = requests.get('http://172.16.121.130:8890/CoCon/Connect')

# 接收回傳結果
self.conn_resp = json.loads(self.conn_resquest.json())

# 印出連線是否建立成功
print(self.conn_resp['Connect'])

# 印出id，每條控制連線的id都不同
print(self.conn_resp['id'])
```

(2) 擷取來自會議主機的封包

當`recording_server.py`建立`cocon_api.py`的`CoConAPI`類別物件時，產生背景執行緒（`packetSniffer`）擷取網路封包
```python
self.packet_sniffing_thread = threading.Thread(target=self.packetSniffer)
self.packet_sniffing_thread.setDaemon(True)
self.packet_sniffing_thread.start()
```
`packetSniffer`函式持續擷取並解析來自會議主機封包
```python
def packetSniffer(self):
    s = time.time()
    # 不斷擷取封包
    while True:
        try:
            # 接收封包
            packet = self.rawSocket.recvfrom(9192)[0]
        except:
            pass

        # parsePacket函式解析封包訊息，如果來自會議主機
        # 而且封包訊息包含麥克風按鈕事件，就回傳封包訊息，否則回傳None
        mic_msg = self.parsePacket(packet)

        # getSpeaker函式從封包訊息得知：
        # 1.剛啟動的麥克風編號，通知該麥克風的執行緒，紀錄當前的frame index
        # 2.剛關閉的麥克風編號，通知該執行緒擷取開啟到關閉時間段的語音訊號
        self.getSpeaker(mic_msg)

        t = time.time()

        # 每經過60秒就重新建立連線，避免斷線
        if t-s >= 60:
            self.createControlConnection()
            s = time.time()
```

(3) 解析封包訊息開啟和關閉的麥克風編號

`parsePacket`函式解析封包，如果來自會議主機，而且封包訊息包含麥克風按鈕事件，就回傳封包訊息，否則回傳`None`
```python
def parsePacket(self, packet):
    ...
    # 如果來源IP是會議主機的IP才繼續處理
    if source_ip == plinux_server_ip:
        # 會議主機回傳的封包中，麥克風資訊是透過TCP協定攜帶，因此要判斷封包是否包含TCP segment
        # IP協定欄位值為6表示IP攜帶的資料是TCP segment
        if ip[6] == 6:
            ...
            # 取出TCP segment攜帶的資料
            tcp_data_len = len(tcp_packet[tcp_length:])

            # 從會議主機傳給本機的TCP封包很多
            # 為了減少判斷的封包量，設定資料長度區間過濾封包
            if self.filterWithDataLength(tcp_data_len):
                try:
                    # 解碼訊息
                    mic_msg = tcp_packet[tcp_length:].decode("UTF-8")
                except:
                    pass
    # 回傳訊息                
    return mic_msg
```

這裡說明含有麥克風按鈕事件的訊息（`mic_msg`）內容，`mic_msg`是`json`格式，可轉換成字典型態取出想要的鍵值。當會議主機偵測到麥克風的按鈕開啟或關閉的事件時，會傳送2種訊息給本機電腦：

* 第1種訊息：`{"MicButtonEvent":{"Event":"<up/down>","SeatNr":<麥克風編號>}}`，從`MicButtonEvent`鍵得知單一支麥克風（`SeatNr`）的按鈕事件（`Event`）
```
# 訊息長度54，編號2的麥克風已按下（up）按鈕
b'"{\\"MicButtonEvent\\":{\\"Event\\":\\"up\\",\\"SeatNr\\":2}}"'

# 訊息長度56，編號2的麥克風已關閉（down）按鈕
b'"{\\"MicButtonEvent\\":{\\"Event\\":\\"down\\",\\"SeatNr\\":2}}"'
```

* 第2種訊息：`{"MicrophoneState":{"Speakers":<已開啟的麥克風清單>,"Requests":<等待開啟麥克風清單，可忽略>,"Replies":<可忽略>}}`，從`MicrophoneState`鍵得知是否有麥克風處於開啟狀態，`Speakers`鍵的`list`存放已開啟(按下按鈕)的麥克風編號
```
# 訊息長度73，表示當前只有編號2的麥克風是開啟狀態（Speakers:[2]）
b'"{\\"MicrophoneState\\":{\\"Speakers\\":[2],\\"Requests\\":[],\\"Replies\\":[]}}"'

# 訊息長度72，表示當前沒有麥克風是開啟狀態（Speakers:[]）
b'"{\\"MicrophoneState\\":{\\"Speakers\\":[],\\"Requests\\":[],\\"Replies\\":[]}}"'
```

`getSpeaker`函式找出剛開啟和關閉的麥克風編號，並且通知各別的麥克風執行緒擷取語音訊號，為了方便程式實作，僅處理含有`MicrophoneState`的訊息（第2種訊息）即可。
```python
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

                # 取出Speakers清單，裡頭紀錄著當前已開啟的麥克風編號
                mic_number_list = mic_msg_dict["MicrophoneState"]["Speakers"]
                list_len = len(mic_number_list)
                print(f"麥克風: {mic_number_list}")
                # 如果清單長度大於0才繼續處理
                if list_len > 0:

                    for mic_number in mic_number_list:

                        if mic_number not in self.mic_set:
                            # 將已開啟的麥克風編號存入集合
                            self.mic_set.add(mic_number)

                            print("=== mic_set add ===")
                            print(self.mic_set)

                            # 如果麥克風不在上一時刻的集合出現，代表該麥克風是剛剛才啟動，
                            # 這時要呼叫reocrding_server.py的錄音執行緒紀錄當前的frame index （start index）
                            if mic_number not in self.previous_mic_set:
                                print(f"getSpeaker act {mic_number}")
                                self.mic_record.get_activated_mic_number(mic_number)

                # 取得剛關閉的麥克風集合
                diff_mic_set = self.previous_mic_set - self.mic_set

                if len(diff_mic_set) > 0:
                    # 每個剛關閉的麥克風都紀錄當前的frame index （stop index）
                    # 呼叫reocrding_server.py的錄音執行緒擷取錄製的語音段
                    for mic_number in diff_mic_set:
                        print(f"getSpeaker inact {mic_number}")
                        self.mic_record.get_inactivated_mic_number(mic_number)

                self.previous_mic_set = self.mic_set.copy()
                self.mic_set.clear()
```

### (二) Recognition server

本小節說明Recognition server的關鍵程式片段，Recognition server負責將GUI送來的語音訊號傳給AI伺服器辨識，然後將辨識結果傳給GUI。
        
#### 1. `recognition_server.py`
 
`recognition_server.py`是flask API server，下列說明`recognition_server.py`重要的程式片段

(1) 主程序

`main`程式碼
```python
if __name__ == '__main__':
    # 初始化process類別，用於傳送語音訊號給AI伺服器
    process = Process()
    print("啟動Recognition Server - port 3000")
    # 啟動server，port 3000
    app.run(threaded=False, port=3000)
```
(2) 傳送語音訊號

`Process`類別負責將語音訊號傳送至AI伺服器並等待辨識結果
```python
class Process():
    # 取得語者辨識結果
    def speaker_id(self, wav):
        ...
    # 取得語音辨識結果
    def speech_MASR(self, wave_path):
        ...
    # 取得摘要生成結果
    def run_summary(self, content):  
        ...        
```

(3) API

API `/postAudioFile`提供GUI呼叫，將GUI送來的音檔訊號資料傳給`Process`類別處理，`Process`類別的函式傳回語者、語音和摘要辨識結果，然後`post_audio_file`函式再將辨識結果傳給GUI
```python
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

    # 語音辨識，這裡會將音檔切成許多段，再逐一傳給process類別的speech_MASR作辨識
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
```

### (三) GUI

本小節說明GUI的關鍵程式片段，GUI定期向Recording server要求一個語音檔名，如果要到語音檔名，就讀取語音檔並傳送語音訊號給Recognition server等待辨識，GUI再將Recognition server回傳的辨識結果呈現在介面上。此外，當GUI要關閉時會儲存會議記錄至資料夾 `YYYY_MM_DD_meeting/`，檔案包含完整的會議音檔和語音逐字稿，檔案名稱如下所示：
* 語者逐字稿檔 `YYYY-MM-DD_HH-mm-ss_會議逐字稿.txt`
* 語者摘要檔 `YYYY-MM-DD_HH-mm-ss_會議紀錄摘要.txt`
* 完整會議語音檔 `YYYY-MM-DD_HH-mm-ss_record_original.wav`
* 語音時間標記檔 `YYYY-MM-DD_HH-mm-ss_record_original.txt`

#### 1. `GUI_product_v2.py`

`GUI_product_v2.py`是圖形介面程式，下列說明`GUI_product_v2.py`重要的程式片段

(1) 主程序

`main`程式碼
```python
if __name__== "__main__":
    # 讀取GUI設定檔
    config = read_config()
    root = Tk()
    # 初始化GUI
    my_gui = NCSISTGUI(root,config)

    my_gui.storeSelfGUIObject(my_gui)

    # 建立執行緒，每隔一段固定時間向Recording server要求一個語音檔名
    # 如果要到語音檔名，就讀語音檔並傳送語音訊號給Recognition server等待辨識
    recog_thread = RecognitionThread(my_gui)
    recog_thread.setDaemon(True)
    recog_thread.start()

    # 開啟GUI
    root.protocol("WM_DELETE_WINDOW", my_gui.on_closing)
    root.mainloop()
```

(2) 初始化GUI變數

`NCSISTGUI`類別初始化的變數
```python
# 初始化要製作會議逐字稿的音檔清單，每當Recognition server回傳1筆辨識結果，用來辨識的音檔會被加進該清單中 
self.meeting_record_audio_list = []

# 建立製作會議記錄的物件，GUI關閉時會呼叫meeting_record.py的函式製作會議紀錄
self.meeting_record = mr.MeetingRecord()

# 呼叫Recording server API初始化要辨識的音檔清單，
# 該清單讓Recording server錄製的音檔名稱能存入，也讓GUI定期拿取
self.initialize_recog_audio_list()
```

(3) 要求語音檔名以及傳送訊號等待辨識

`RecognitionThread`執行緒定期向Recording server要求一個語音檔名，如果要到語音檔名，就讀語音檔並傳送語音訊號給Recognition server等待辨識
```python
class RecognitionThread(threading.Thread):
    # 預設1秒鐘要1筆音檔
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

                # 如果有收到最新的音檔才繼續處理
                if "audio_file" in resp_dict.keys():
                    audio_file = resp_dict["audio_file"]

                    # 傳送語音訊號給Recognition server
                    try:
                        url = recognition_server_ip_port + "/postAudioFile"
                        wav, sr = librosa.load(audio_file, sr=16000)

                        data = {"wav": wav.tolist(), "sr": sr}
                        resp = requests.post(url, json=data)
                        # 接收recognition_server回傳的辨識結果
                        resp_dict = json.loads(resp.text)
                        # 在介面呈現辨識結果
                        self.gui.showRecognizedResult(resp_dict, True)
                        # 紀錄要製作會議逐字稿的檔案清單
                        self.gui.meeting_record_audio_list.append(audio_file)
                        print(f"audio {audio_file}")

                    except:
                        # 如果Recognition server沒有開啟，會進到這個block
                        # 在介面上的語音逐字稿欄位顯示"Recognition Server未開啟"訊息
                        print("Recognition Server未開啟")
                        print("python recognition_server.py")
                        data = {}
                        data["speaker"] = ""
                        data["speech"] = ["Recognition Server未開啟"]
                        data["summary"] = ""
                        self.gui.showRecognizedResult(data, False)

                request_audio_time = time.time()
```

(4) 呈現辨識結果

`showRecognizedResult`函式將語者、語音和摘要呈現在介面上
```python
    # 將辨識結果呈現在GUI上
    # 如果recognition_server有開啟，saving_flag要傳入True，反之要傳入False
    def showRecognizedResult(self, recognized_result_dict, saving_flag):
        # 顯示語音逐字稿
        if "speech" in recognized_result_dict.keys():
            speech = recognized_result_dict["speech"]
            content_rows, result = self.output_speech(speech)
        # 顯示語者
        if "speaker" in recognized_result_dict.keys():
            speaker = recognized_result_dict["speaker"]
            self.output_speaker(speaker, content_rows)
        # 顯示摘要
        if "summary" in recognized_result_dict.keys():
            summary = recognized_result_dict["summary"]
            self.output_summary(summary, content_rows)

        # 如果recognition_server有開啟，會進到這個block，儲存會議記錄字串
        if saving_flag:
            speech = "".join(speech)
            # 儲存字串：語者\t逐字稿\n 
            self.meeting_record.saveMasrResult(speaker, speech)
            # 儲存字串：語者\t摘要\n
            self.meeting_record.saveSummary(speaker, summary)

        self.master.update()
```

(5) 製作會議記錄

當`GUI_product_v2.py`要關閉時，呼叫`meeting_record.py`的函式儲存會議記錄
```python
    # 當使用者點擊GUI上的"關閉"(X)時，會進入on_closing函式
    def on_closing(self):
        print("即將關閉GUI ...")
        print("將會議記錄寫檔")

        # 串接音檔並製作語音時間標記檔，存檔至YYYY-MM-DD_meeting/
        self.meeting_record.concatenateRecordFile(self.meeting_record_audio_list)

        # 寫入會議記錄至YYYY-MM-DD_meeting/
        self.meeting_record.writeMeetingRecord()

        # 初始化會議紀錄
        self.meeting_record.clearRecord()
        
        # 關閉GUI
        self.master.destroy()
```


#### 2. `meeting_record.py`

`meeting_record.py`負責製作會議記錄，下列說明`GUI_product_v2.py`重要的程式片段

(1) 串接音檔並製作時間標記檔

`concatenateRecordFile`函式串接會議語音檔`YYYY-MM-DD_HH-mm-ss_record_original.wav`與製作語音時間標記檔`YYYY-MM-DD_HH-mm-ss_record_original.txt`，語音時間標記檔紀錄音檔的起始發言時間、結束發言時間、語者和逐字稿，用逗號分隔。
```python
data = []
# meeting_record_audio_list紀錄辨識成功的音檔清單
# label_speaker_list紀錄各音檔的語者
# label_asr_list紀錄各音檔逐字稿
for f,speaker,asr in zip(meeting_record_audio_list, self.label_speaker_list, self.label_asr_list):
    w = wave.open(f, 'rb')
    # 取得音檔長度
    audio_duration = w.getnframes() / w.getframerate()

    audio_duration += audio_previous_time
    # 串接音檔時間點對應語者和語音逐字稿的字串
    record_label_line = str(audio_previous_time) + "," + str(audio_duration) + "," + speaker + "," + asr + "\n"

    f1.write(record_label_line)

    audio_previous_time = audio_duration
    # 串接音檔
    data.append([w.getparams(), w.readframes(w.getnframes())])
    w.close()

output = wave.open(self.save_wave_name, 'wb')
output.setparams(data[0][0])

for i in range(len(data)):
    output.writeframes(data[i][1])

output.close() # close audio file
f1.close() # close label file
```

(2) 會議紀錄寫檔

`writeMeetingRecord`函式寫入語者逐字稿檔`YYYY-MM-DD_HH-mm-ss_會議逐字稿.txt`和語者摘要檔`YYYY-MM-DD_HH-mm-ss_會議紀錄摘要.txt`
```python
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
```
