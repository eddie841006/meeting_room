# -*- coding:UTF-8 -*-

from __future__ import print_function
import BIC.speech_segmentation as bic_seg

def cut_wave(wav_nam,save_file):
    frame_size = 256
    frame_shift = 128
    sr = 16000
    
    
    seg_point = bic_seg.multi_segmentation(wav_nam, sr, frame_size, frame_shift,save_file, plot_seg=False, save_seg=True,
                                       cluster_method='bic')
    print('The segmentation point for this audio file is listed (Unit: /s)', seg_point)
    

    



