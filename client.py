################################################
# z5310210 - Jeffery Pan - COMP3331 Assignment #
################################################

from socket import *
from threading import Thread
import sys, json, random, os

def main():
    if len(sys.argv) != 4:
        print("> Usage: python3 client.py server_IP server_port client_udp_server_port")
        sys.exit(1)

    serverHost = sys.argv[1]
    serverPort = int(sys.argv[2])
    udpPort = int(sys.argv[3])    

    # connect to TCP server
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverHost, serverPort))    
    clientName = login(clientSocket, udpPort)

    # set up device as UDP server
    udpRecvThread = UdpRecvThread(udpPort)
    udpRecvThread.start()
    
    # start cmd prompt loop
    tcpThread = TcpThread(clientName, clientSocket, udpRecvThread)
    tcpThread.start()

def login(clientSocket, udpPort):
    while True:
        username = input("> Username: ")
        password = input("> Password: ")
        request = {
            "action": "login",
            "username": username,
            "password": password
        }
        requestDump = json.dumps(request)
        clientSocket.sendall(requestDump.encode())

        receivedMsg = clientSocket.recv(1024).decode()
        if receivedMsg == "success":
            print("> Welcome!")
            clientSocket.sendall(str(udpPort).encode())
            return username
        elif receivedMsg == "fail":
            print("> Invalid Password. Please try again.")
        elif receivedMsg == "fails exceeded":
            print("> Invalid Password. Your account has been blocked. Please try again later.")
            exit()
        elif receivedMsg == "blocked":
            print("> Your account is blocked due to multiple authentication failures. Please try again later.")
            exit()
        else:
            return

class TcpThread(Thread):
    def __init__(self, clientName, clientSocket, udpThread):
        Thread.__init__(self)
        self.clientSocket = clientSocket
        self.clientName = clientName
        self.udpThread = udpThread
        self.isActive = True

    def run(self):
        validCmds = ["EDG", "UED", "SCS", "DTE", "AED", "OUT", "UVF"]
        # command prompt loop
        while self.isActive:
            inputStr = input("\n> Enter one of the following commands (EDG, UED, SCS, DTE, AED, OUT, UVF): \n>>> ")
            cmd = inputStr.split(' ')[0]

            if cmd and cmd not in validCmds:
                print("> Error: Invalid command")
                continue

            # try to exec command. continue if unsuccessful
            if cmd == "EDG" and (not self.doEDG(inputStr)):
                continue
            elif cmd == "UED" and (not self.doUED(inputStr)):
                continue
            elif cmd == "SCS" and (not self.doSCS(inputStr)):
                continue
            elif cmd == "DTE" and (not self.doDTE(inputStr)):
                continue
            elif cmd == "AED":
                self.doAED() 
            elif cmd == "UVF" and (not self.doUVF(inputStr)):
                continue
            elif cmd == "OUT":
                self.logout()
                self.udpThread.stop()
                os._exit(0)
                
    def doEDG(self, inputStr):
        if len(inputStr.split(' ')) != 3:
            print("> Usage: EDG fileId dataAmount")
            return False
        fileId = inputStr.split(' ')[1]
        dataAmount = inputStr.split(' ')[2]
        if not (fileId.isdigit() and dataAmount.isdigit()):
            print("> Error: The fileID and dataAmount parameters must be integers")
            return False
        
        print(f"> The edge device is generating {dataAmount} samples...")
        dataAmount = int(dataAmount)

        with open(f"{self.clientName}-{fileId}.txt", "w+") as f:
            for i in range(dataAmount):
                f.write(str(random.randint(1, dataAmount)) + "\n")
        print(f"> Data generation done, {dataAmount} data samples have been generated and stored in the file ({self.clientName}-{fileId}.txt)")
        return True

    def doUED(self, inputStr):
        if len(inputStr.split(' ')) != 2:
            print("> Usage: UED fileId")
            return False

        fileId = inputStr.split(' ')[1]
        if not fileId.isdigit():
            print("> Error: The fileID must be an integer")
            return False

        fileName = ""
        
        for file in os.listdir():
            if file.endswith(f"-{fileId}.txt"):
                fileName = file
        
        if not fileName:
            print("> Error: Specified file does not exist.")
            return False 
        
        with open(fileName, "r") as f:
            data = f.read()
            # send request to server
            request = {
                "action": "ued",
                "fileId": int(fileId),
                "fileName": fileName,
                "data": data
            } 
            sendJsonObject(request, self.clientSocket)

        # decode response from server and print outcome to terminal
        receivedMsg = self.clientSocket.recv(1024).decode()
        if receivedMsg == "success":
            print(f"> file ({fileName}) uploaded to server")
            return True
        else: 
            print(f"> Error: file upload failed")
            return False

    def doSCS(self, inputStr):
        if len(inputStr.split(' ')) != 3:
            print("> Usage: SCS fileId computationOperation")
            return False

        fileId = inputStr.split(' ')[1]
        if not fileId.isdigit():
            print("> Error: The fileID must be an integer")
            return False
        
        availOps = ["SUM", "AVERAGE", "MAX", "MIN"]
        operation = inputStr.split(' ')[2]
        if operation not in availOps:
            print("> Error: Invalid operation. Available operations: SUM, AVERAGE, MAX, MIN")
            return False
        
        # send request to server
        request = {
            "action": "scs",
            "fileId": int(fileId),
            "operation": operation
        } 

        sendJsonObject(request, self.clientSocket)
        
        # decode response from server and print outcome to terminal
        receivedMsg = self.clientSocket.recv(1024).decode()
        if not receivedMsg.startswith("fail"):
            print(receivedMsg)
            return True
        elif "DNE" in receivedMsg:
            print("> Error: Specified file does not exist.")
            return False
       
        return False

    def doDTE(self, inputStr):
        if len(inputStr.split(' ')) != 2:
            print("> Usage: DTE fileId")
            return False

        fileId = inputStr.split(' ')[1]
        if not fileId.isdigit():
            print("> Error:  The fileID must be an integer")
            return False  
        
        # send request to server
        request = {
            "action": "dte",
            "fileId": int(fileId)
        } 
        sendJsonObject(request, self.clientSocket)
        
        # decode response from server and print outcome to terminal
        receivedMsg = self.clientSocket.recv(1024).decode()
        if not receivedMsg.startswith("fail"):
            print(f"> file ({receivedMsg}) deleted from server")
            return True
        elif "DNE" in receivedMsg:
            print("> Error: Specified file does not exist.")
            return False

    def doAED(self):
        request = {"action": "aed"} 
        sendJsonObject(request, self.clientSocket)

        receivedMsg = self.clientSocket.recv(1024).decode()
        responseDict = json.loads(receivedMsg)
        if not responseDict:
            print("> No other active edge devices")
        
        print("Other active devices:")
        for device, info in responseDict.items():
            ipAddr = info["ip"]
            port = info["udpPort"]
            timeJoined = info["timeJoined"]
            print(f"    {device}; {ipAddr}; {port}; active since {timeJoined}")
        return True

    def doUVF(self, inputStr):
        if len(inputStr.split(' ')) != 3:
            print("> Usage: UVF deviceName filename")
            return False
        
        deviceName = inputStr.split(' ')[1]

        request = {"action": "aed"} 
        sendJsonObject(request, self.clientSocket)
        receivedMsg = self.clientSocket.recv(1024).decode()
        responseDict = json.loads(receivedMsg)
        if deviceName not in responseDict:
            print(f"> Error: {deviceName} is either offline, or self")
            return False

        fileName = inputStr.split(' ')[2]
        recvPort = int(responseDict[deviceName]["udpPort"])

        #start new thread for sending udp packets
        sendFile(fileName, recvPort, self.clientName)
        return True

    def logout(self):
        request = {"action": "out"}
        sendJsonObject(request, self.clientSocket)
        self.isActive = False
        print("\n> Thanks for using client.py. See you soon :D")
        
def sendFile(fileName, recvPort, senderName):
    senderSocket = socket(AF_INET, SOCK_DGRAM)
    recvAddress =  ("localhost", recvPort)
    
    fileNameNew = f"{senderName}_{fileName}"

    # send file name first
    senderSocket.sendto(fileNameNew.encode(), recvAddress)

    # send file contents in packets of length 1024 bytes
    with open(fileName, "rb") as f:
        packetData = f.read(1024)
        while packetData:
            senderSocket.sendto(packetData, recvAddress)
            packetData = f.read(1024)
    
    print(f"> {fileName} has been uploaded")
    senderSocket.close()

def sendJsonObject(object, clientSocket):
    requestDump = json.dumps(object)
    clientSocket.sendall(requestDump.encode()) 

class UdpRecvThread(Thread):
    def __init__(self, UdpPort):
        Thread.__init__(self)
        self.UdpPort = UdpPort
        self.isAlive = True
        print(f"> Receiving on UDP Port: {UdpPort}")
    
    def run(self):
        sock = socket(AF_INET,SOCK_DGRAM)
        addressSelf = ("localhost", self.UdpPort)
        sock.bind(addressSelf)

        while self.isAlive:
            # receive file name
            data, address = sock.recvfrom(1024)
            recvFileName = data.decode()
            # receive contents
            with open(recvFileName, "wb") as f:
                data, address = sock.recvfrom(1024)
                try:
                    while data:
                        f.write(data)
                        sock.settimeout(5)
                        data, address = sock.recvfrom(1024)
                except timeout:
                    sock.settimeout(None)
                    print(f"\n> Received {recvFileName.split('_')[1]} from {recvFileName.split('_')[0]}")
                    print("\n> Enter one of the following commands (EDG, UED, SCS, DTE, AED, OUT, UVF): \n>>> ")
        sock.close()
    
    def stop(self):
        self.isAlive = False
                    
main()