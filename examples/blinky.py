import dali_interface
import time


frame_recall_max = dali_interface.DaliFrame(length=16, data=0xff05)
frame_off = dali_interface.DaliFrame(length=16, data=0xff00)

dali_connection = dali_interface.DaliUsb()

while True:
    dali_connection.transmit(frame_recall_max, True)
    time.sleep(0.75)
    dali_connection.transmit(frame_off, block=True)
    time.sleep(0.75)
