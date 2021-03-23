import wave
from os import walk
from os.path import join
import os




def main():
    record_file_list = []
    record_file_path = "all_records"


    for root, dirs, files in walk(record_file_path):
        for f in files:
            record_file = join(record_file_path, f)
            print(record_file)
            record_file_list.append(record_file)


    data = []
    for f in record_file_list:
        w = wave.open(f, 'rb')
        data.append([w.getparams(), w.readframes(w.getnframes())])
        w.close()

    outfile = "so.wav"
    output = wave.open(outfile, 'wb')
    output.setparams(data[0][0])

    for i in range(len(data)):
        output.writeframes(data[i][1])

    output.close()

    try:
        for file in record_file_list:
            os.remove(file)
    except OSError as e:
        print(e)


if __name__ == "__main__":
    main()