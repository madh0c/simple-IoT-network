################################################
# z5310210 - Jeffery Pan - COMP3331 Assignment #
################################################


from socket import *
from threading import Thread
from datetime import datetime
import sys, json, os

maxLoginAttempts = 3
activeUsers = {}
failedLogins = {}
blockedUsers = {}

def main():
    if len(sys.argv) != 3:
        print("> Usage: python3 server.py server_port number_of_consecutive_failed_attempts")
        exit(1)
    
    # set max number_of_consecutive_failed_attempts before blocking the user
    global maxLoginAttempts
    if not sys.argv[2].isdigit():
        print(f"> Invalid number of allowed failed consecutive attempts:{sys.argv[2]}. This argument must be an integer.")
    else: 
        maxLoginAttempts = int(sys.argv[2])

    if (maxLoginAttempts < 1) or (maxLoginAttempts > 5):
        print(f"> Invalid number of allowed failed consecutive attempts:{sys.argv[2]}. Integer must be between 1 and 5.")
    
    # clear active devices log
    open("edge-device-log.txt", "w").close()

    # start TCP server
    serverPort = int(sys.argv[1])
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.bind(("localhost", serverPort))

    print(f"> Server is running on port: {serverPort}")
    print("> Awaiting connections...")

    # wait for connections
    while True:
        serverSocket.listen()
        clientSocket, clientAddress = serverSocket.accept()
        clientThread = ClientThread(clientAddress, clientSocket)
        clientThread.start()

class ClientThread(Thread):
    def __init__(self, clientAddress, clientSocket):
        Thread.__init__(self)
        self.clientAddress = clientAddress
        self.clientSocket = clientSocket
        self.clientAlive = False
        self.clientName = None

        print(f"> New connection created for: {self.clientAddress}")
        self.clientAlive = True
        
    def run(self):
        while self.clientAlive:
            message = self.clientSocket.recv(1024)

            if not message:
                self.clientAlive = False
                print(f"> {self.clientAddress} has disconnected")
                break

            reqDict = json.loads(message.decode())
            action = reqDict.get("action")

            if action == "login":
                self.processLogin(reqDict.get("username"), reqDict.get("password"))
            else:
                print(f"> Edge device {self.clientName} issued a {action.upper()} command")

            if action == "ued":
                self.processUED(reqDict.get("fileId"), reqDict.get("fileName"), reqDict.get("data"))
            elif action == "scs":
                self.processSCS(reqDict.get("fileId"), reqDict.get("operation")) 
            elif action == "dte":
                self.processDTE(reqDict.get("fileId"))
            elif action == "aed":
                self.processAED()
            elif action == "out":
                self.processLogout()
            
    def processLogin(self, username, password):
        print(f"> New login request from: {self.clientAddress}")
        
        global blockedUsers, failedLogins

        if username in blockedUsers:
            timeOfBlock = blockedUsers[username]
            delta = datetime.now() - timeOfBlock
            if delta.total_seconds() < 10:
                self.clientSocket.send("blocked".encode())
                return
            else:
                del blockedUsers[username]

        credentialsDict = {}
        with open("credentials.txt", "r") as f:            
            for line in f.read().splitlines():
                usr = line.split(' ')[0]
                pwd = line.split(' ')[1]
                credentialsDict[usr] = pwd

        if username in credentialsDict and credentialsDict[username] == password:
            self.clientSocket.send("success".encode())
            print(f"> {username} logged in from {self.clientAddress}")

            # add username to class
            self.clientName = username

            # write to active devices log
            message = self.clientSocket.recv(1024)
            clientUdpPort = message.decode()
            seqNo = 0
            with open("edge-device-log.txt", "r") as f:
                seqNo = len(f.readlines()) + 1
            with open("edge-device-log.txt", "a") as f:    
                datetimeStr = datetime.now().strftime("%d %B %Y %X")
                f.write(f"{seqNo}; {datetimeStr}; {username}; {self.clientAddress[0]}; {clientUdpPort}\n")

            # add user's info to dict of currently active users
            global activeUsers
            activeUsers[username] = {
                "ip": self.clientAddress[0],
                "udpPort": clientUdpPort,
                "timeJoined": datetime.now().strftime("%d %B %Y %X")
            }
        else:
            global maxLoginAttempts
            failedLogins[username] = 1 if username not in failedLogins else failedLogins[username] + 1
            if failedLogins[username] >= maxLoginAttempts:
                del failedLogins[username]
                blockedUsers[username] = datetime.now()
                print(f"> {self.clientName} blocked for 10s")
                self.clientSocket.send("fails exceeded".encode())
            else:
                print(f"Login incorrect. {maxLoginAttempts - failedLogins[username]} attempts remaining.")
                self.clientSocket.send("fail".encode())

    def processUED(self, fileId:int, fileName, data):        
        with open(fileName, "w+") as f:
            f.write(data)
        
        print(f"> file ({fileName}) received from {self.clientName} {self.clientAddress}")
        
        # upload log
        with open ("upload-log.txt", "a") as f:
            datetimeStr = datetime.now().strftime("%d %B %Y %X")
            dataAmount = len(data.splitlines())
            f.write(f"{self.clientName}; {datetimeStr}; {fileId}; {dataAmount}" + "\n")

        self.clientSocket.send(f"success".encode())

    def processSCS(self, fileId, operation):
        fileName = ""
        
        for file in os.listdir():
            if file.endswith(f"-{fileId}.txt"):
                fileName = file
        
        if not fileName:
            print("> Failed: specified file does not exist")
            self.clientSocket.send("fail DNE".encode())
            return
        
        with open(fileName, "r") as f:
            listInts = [int(x) for x in f.read().splitlines()]
            if operation == "SUM":
                message = str(sum(listInts))  
            elif operation == "AVERAGE":
                message = str(sum(listInts) / len(listInts))
            elif operation == "MAX":
                message = str(max(listInts))
            elif operation == "MIN":
                message = str(min(listInts))
            
            self.clientSocket.send(message.encode())
        print(f"> {operation} performed on ({fileName}). Result of {message} was sent to the client.")

    def processDTE(self, fileId):
        fileName = ""
        
        for file in os.listdir():
            if file.endswith(f"-{fileId}.txt"):
                fileName = file
        
        if not fileName:
            print("> Failed: specified file does not exist")
            self.clientSocket.send("fail DNE".encode())
            return
        
        # upload log
        data = None
        with open(fileName, "r") as f:
            data = f.read().splitlines()
        with open("deletion-log.txt", "a") as f:
            datetimeStr = datetime.now().strftime("%d %B %Y %X")
            dataAmount = len(data)
            f.write(f"{self.clientName}; {datetimeStr}; {fileId}; {dataAmount}" + "\n")
        
        os.remove(fileName)
        print(f"> file ({fileName}) deleted from database")
        self.clientSocket.send(fileName.encode())
        
    def processAED(self):
        global activeUsers
        response = activeUsers.copy()
        del response[self.clientName]
        responseDump = json.dumps(response)
        self.clientSocket.sendall(responseDump.encode())
    
    def processLogout(self):
        self.clientSocket.close()
        self.clientAlive = False
        print(f"> user {self.clientName} has logged out.")
        print(f"> Connection with {self.clientAddress} closed.")
        # update active device log
        newLog = ""
        with open("edge-device-log.txt", "r") as f:
            i = 1
            for line in f.readlines():
                if line.split("; ")[2] != self.clientName:
                    newLog = newLog + str(i) + line[1:]
                    i += 1
        with open("edge-device-log.txt", "w") as f:
            f.write(newLog)

        # update active device dict
        global activeUsers
        del activeUsers[self.clientName]
main()
