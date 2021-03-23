import pyaudio as pa


def main():
    mic_device_name = ['DVS Receive  1-2 (Dante Virtual', 'DVS Receive  3-4 (Dante Virtual', 'DVS Receive  5-6 (Dante Virtual']
    mic_device_name += ['DVS Receive  7-8 (Dante Virtual', 'DVS Receive  9-10 (Dante Virtua']
    pya = pa.PyAudio()

    print("====== 所有音訊裝置 ======")
    for i in range(20): #pya.get_device_count()
        print( pya.get_device_info_by_index(i) )


    print("====== Dante虛擬音效卡 ======")
    for i in range(30):
        try:
            device_dict = pya.get_device_info_by_index(i)
            for mic_device in mic_device_name:
                if mic_device == device_dict["name"]:
                    print(device_dict)
            # print()
        except:
            print("")


if __name__ == "__main__":
    main()