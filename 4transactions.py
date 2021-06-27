import socket
import sys
import subprocess
import re, time

BUFFER_SIZE = 1024

#Note: Orchestrator IP address and port-> 18.139.29.142:4650
arguments = sys.argv


a = arguments[2] #ip address
p = int(arguments[4]) #port number
f = arguments[6] #filename
m = int(arguments[8]) #mode of the load balancing
s = int(arguments[10]) #selected server if non-load-balancing is chosen
print("LIst of arguments: ", arguments)

#fetch the data from the text file
file = open(f,"r") 
payload = file.read()

s = 0
comparisons = {} 
successfulTest = 0
shouldretry = False
while True:
    if successfulTest == 0 and not(shouldretry):
        m = 1
    elif shouldretry:
        shouldretry = False
    else:
        m = 2
        s+=1
    #setting up udp
    clientSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #Send intent message to the orchestrator
    print("### Sending intent message to the orchestrator ###")
    intentMessage = "Type:0;"
    clientSock.sendto(intentMessage.encode(), (a,p))
    print("Intent message sent!")

    #waiting for orchestrator server message Type 1 message
    result, addr = clientSock.recvfrom(BUFFER_SIZE)
    result  = result.decode() 
    print("Orchestrator's message received! Orchestrator's message:")
    print(result)
    print()

    #extracting the information from the orchestrator's message 
    result = result.split(';')
    messageType = int(result[0][-1]) #Type of the message
    if(messageType != 1):
        print("Wrong message from the orchestrator!")
        clientSock.close()
        shouldretry = True
        continue
    messageTID = int(result[1][4:]) #TID of the message
    #extracting the list of ip addresses 
    ipAddressSTR = (result[2][8:-3]).split("'}, {'") 
    ipAddresses = []
    for i in ipAddressSTR: #this loop will extract the ipaddress and the server name of the ipaddress
        serverInfo = i.split("', '")
        temp = []
        temp.append(serverInfo[0][14:]) #server's ip address
        temp.append(serverInfo[1][8:]) #server's name 
        ipAddresses.append(temp)
    print("List of Ip addresses are extracted: ")
    print(ipAddresses)

    startTime = time.perf_counter()
    timeout = time.perf_counter()
    def sendMessage(ip, p, payloads, start, payloadperServer, seq):    
        sent = start #sent indicates how much of data are sent already
        last = False #this variable will tell the function if it is already sending the last batch of data
        while sent < start+payloadperServer:
            if ((start+payloadperServer)-sent) > 100: #if the remaining data to be sent has more than 100 charaters
                data = payloads[sent:(sent+100)]
            else: #last batch of data to send
                last = True
                data = payloads[sent:(start+payloadperServer)]
            message = "Type:2;TID:{0};SEQ:{1};DATA:{2}".format(messageTID, seq, data) #message to send
            clientSock.sendto(message.encode(), (ip,p))
            #wait for ack
            while True:
                if (time.perf_counter() - timeout > 120):
                    print("Timeout occured!")
                    return -1
                clientSock.settimeout(3)
                try: 
                    result, addr = clientSock.recvfrom(BUFFER_SIZE) #if ack is received, break the loop
                    break
                except socket.timeout: # if timeout, repeat sending
                    clientSock.sendto(message.encode(), (ip,p))

            result = result.decode()
            result = result.split(';')
            messageType = result[0][-1]
            messagetid = result[1][4:]
            messageSeq = result[2][4:]
            print("Sending to {0}".format(ip))
            print("start index: {0}\npayloadlength: {1}\nseq: {2}\nmessageType: {3}\nmessageTID: {4}\nmessageSeq: {5}".format(sent, payloadperServer,seq, messageType,messagetid,messageSeq))
            print()
            if int(messageSeq) != seq or int(messageType) != 3 or int(messagetid) != messageTID:
                print("Failed transmission. Problem occured.")
                return -1
            if last: 
                sent = start + payloadperServer #update "sent" variable
            else:
                sent += 100 #update "sent" variable
            seq += 1 #increment seq number after a successful sending.
        return seq

    if m == 1: #load balancing mode will be used
        print("\nMODE: LOAD-BALANCING")
        #calculating the latencies of each server for load balancing
        latencies = []
        for i in ipAddresses:
            output = subprocess.check_output(['ping','-c', '3', i[0]]).decode()
            lat_value = re.search("rtt min/avg/max/mdev = (\d+.\d+)/(\d+.\d+)/(\d+.\d+)/(\d+.\d+)", output).group(2)
            print(lat_value)
            latencies.append(int(float(lat_value))) #the element at index 1 is the average latency
        print("Latencies computed (format-> [Server1, Server2, Server3]): ")
        print(latencies)

        
        '''
        computation for load balacing
        for each server they will initially receive 10% of the payload, then we will divide the remaining 70% of the payload
        based from the servers' ratios
        '''
        load_balance = [0,0,0]
        summ = sum(latencies)
        maxim = max(latencies)
        minim = min(latencies)
        for i in range(len(latencies)):
            if latencies[i] == maxim: #server with the maximum delay will receive minimum ratio + 10
                load_balance[i] = (minim/summ)*70 + 10
            elif latencies[i] == minim: ##server with the least delay will receive max ratio + 10
                load_balance[i] = (maxim/summ)*70 + 10
            else:
                load_balance[i] = (latencies[i]/summ)*70+10
        print("Resulting load-balance (percentage of data each server will receive):")
        print(load_balance)

        print("\n### SENDING THE DATA TO THE SERVERS ###")
        counter = 1
        start = 0
        seq = 0
        length = len(payload)
        if length < 3:#handle edge cases less than 3 bytes(characters) of data
            print("Not Acceptable. Size of data is too small.")
            sys.exit
        for ip in ipAddresses:
            ipadd = ip[0]
            if counter == 3: #if we are sending to the last server, we will send all remaining data
                payloadperServer = length-start
            else:
                payloadperServer = int(load_balance[counter-1]/100 * (length-3)+1) 
            seq = sendMessage(ipadd, p, payload, start, payloadperServer, seq) #send data
            if seq == -1:
                shouldretry = True
                break

            start += payloadperServer #update start (also indicates how many data are sent already)
            counter+=1 #increment counter

        if shouldretry:
            clientSock.close()
            continue #error/timeout occured repeat the process (retry sending) 

    elif m == 2: #No load balancing would be done, we will use the s to choose the server
        print("\nMODE: NON-LOAD-BALANCING")
        nonLoadBal = ipAddresses[(s-1)][0]
        seq = 0
        length = len(payload)
        print("\n### SENDING THE DATA TO THE SELECTED SERVER ###")
        seq = sendMessage(nonLoadBal, p, payload, 0, length, seq)
        if seq == -1:
            shouldretry = True
            clientSock.close()
            continue #error/timeout occured repeat the process (retry sending)

    timeFinished = time.perf_counter() - startTime

    print("Finish!")
    clientSock.close()

    if s == 0:
        ip_add = ''
        for j in ipAddresses:
            ip_add += (j[0] + "/ ")
    else:
        ip_add = ipAddresses[s-1][0]

    comparisons[successfulTest] = (m, s, ip_add, timeFinished, seq)
    successfulTest += 1

    if successfulTest > 3:
        break

for i in comparisons:
    print("Test {0}:".format(i))
    print("\tmode: ",comparisons[i][0])
    print("\tselected server (for non-balancing mode): ",comparisons[i][1])
    print("\tServer(s): ",comparisons[i][2])
    print("\tTime it take to send the data: ",comparisons[i][3])
    print("\tTotal packets sent: ",comparisons[i][4])
