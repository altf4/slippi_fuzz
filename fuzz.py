#!/usr/bin/python3
import argparse
import json
import enet
import sys
import random
import time

parser = argparse.ArgumentParser(description='Slippi Online network fuzzer')
parser.add_argument('--user', '-u',
                    help='Path to user.json file',
                    required=True,
                    default=None)
parser.add_argument('--opponent', '-o',
                    help='Connect code of opponent',
                    required=True,
                    default=None)
parser.add_argument('--seed', '-s',
                    help='Use manual seed to repeat a previous run',
                    default=None)

args = parser.parse_args()
with open(args.user) as f:
  user_json = json.load(f)

if args.seed is not None:
    seed = int(args.seed)
else:
    seed = int(time.time() * 1000)
print("using seed: ", seed)
random.seed(seed)

class Pad:
    def __init__(self):
        self.messageId = 0x80
        self.frame = 0x00000000
        self.playerIdx = 0x00
        # Then contains N pads (each 8 bytes)
        self.pads = [0x0000000000000000]

class PadAck:
    def __init__(self):
        self.messageId = 0x81
        self.frame = 0x00000000
        self.playerIdx = 0x00

class PlayerSelections:
    def __init__(self):
        self.messageId = 0x82
        self.characterId = 0x07
        self.characterColor = 0
        self.isCharacterSelected = 1
        self.playerIdx = 0
        self.stageId = 3
        self.isStageSelected = 1
        self.rngOffset = 0x12345678
        self.teamId = 0

    def randomize(self):
        self.messageId = 0x82
        self.characterId = random.getrandbits(8)
        self.characterColor = random.getrandbits(8)
        self.isCharacterSelected = random.getrandbits(8)
        self.playerIdx = random.getrandbits(1)
        self.stageId = random.getrandbits(16)
        self.isStageSelected = random.getrandbits(8)
        self.rngOffset = random.getrandbits(32)
        self.teamId = random.getrandbits(8)

    def to_buffer(self):
        paramlist = []
        paramlist.append((self.messageId).to_bytes(1, byteorder='big'))
        paramlist.append((self.characterId).to_bytes(1, byteorder='big'))
        paramlist.append((self.characterColor).to_bytes(1, byteorder='big'))
        paramlist.append((self.isCharacterSelected).to_bytes(1, byteorder='big'))
        paramlist.append((self.playerIdx).to_bytes(1, byteorder='big'))
        paramlist.append((self.stageId).to_bytes(2, byteorder='big'))
        paramlist.append((self.isStageSelected).to_bytes(1, byteorder='big'))
        paramlist.append((self.rngOffset).to_bytes(4, byteorder='big'))
        paramlist.append((self.teamId).to_bytes(1, byteorder='big'))
        return b"".join(paramlist)

class ConnSelected:
    def __init__(self):
        self.messageId = 0x83
        # No other fields

class ChatMessage:
    def __init__(self):
        self.messageId = 0x84
        self.chatMessage = 0x00000000
        self.playerIdx = 0x00

    def randomize(self):
        self.messageId = 0x84
        self.chatMessage = random.getrandbits(32)
        self.playerIdx = random.getrandbits(8)

    def to_buffer(self):
        paramlist = []
        paramlist.append((self.messageId).to_bytes(1, byteorder='big'))
        paramlist.append((self.chatMessage).to_bytes(4, byteorder='big'))
        paramlist.append((self.playerIdx).to_bytes(1, byteorder='big'))
        return b"".join(paramlist)

# Connect to MM server
host = enet.Host(None, 1, 0, 0)
peer = host.connect(enet.Address(bytes("mm.slippi.gg", 'utf-8'), 43113), 1)
print("Connecting to MM server...")

event = host.service(1000)
if event.type == enet.EVENT_TYPE_CONNECT:
    request = {}
    request["type"] = "create-ticket"
    request["user"] = {"uid": user_json["uid"], "playKey": user_json["playKey"]}
    request["search"] = {"mode": 2, "connectCode": [ord(s) for s in args.opponent]}
    request["appVersion"] = "2.3.1"
    peer.send(0, enet.Packet(bytes(json.dumps(request), 'utf-8')))
else:
    print("Failed to get ticket from MM server")
    sys.exit(1)

# Wait for match with opponent
while True:
    event = host.service(2000)
    event_type = event.type

    if event.type == enet.EVENT_TYPE_NONE:
        print("Waiting to be connected with opponent...")
    elif event.type == enet.EVENT_TYPE_RECEIVE:
        response_ticket = json.loads(event.packet.data)
        print(response_ticket)
        if response_ticket["type"] == "get-ticket-resp":
            break
    elif event.type == enet.EVENT_TYPE_CONNECT:
        print("how")
    elif event.type == enet.EVENT_TYPE_DISCONNECT:
        print("Disconnecting")

# Now we connect to the opponent directly
peer.disconnect()
del peer
peer = None
del host
host = None

for player in response_ticket["players"]:
    if player["uid"] != user_json["uid"]:
        opponent_ip = player["ipAddress"].split(":")[0]
        opponent_port = player["ipAddress"].split(":")[1]
    else:
        our_port = player["ipAddress"].split(":")[1]

host = enet.Host(enet.Address(b"0.0.0.0", int(our_port)), 1, 0, 0)
peer = host.connect(enet.Address(bytes(opponent_ip, 'utf-8'), int(opponent_port)), 1)

# Wait for match with opponent
connected = False
wait_time = 2000
while True:
    if connected:
        wait_time = 50
    event = host.service(wait_time)
    event_type = event.type

    if connected:
        chat = ChatMessage()
        chat.randomize()
        peer.send(0, enet.Packet(chat.to_buffer()))

    if event.type == enet.EVENT_TYPE_NONE:
        pass
    elif event.type == enet.EVENT_TYPE_RECEIVE:
        print("Data")
    elif event.type == enet.EVENT_TYPE_CONNECT:
        print("Connected to opponent!")
        print("Fuzzing messages...")
        connected = True
    elif event.type == enet.EVENT_TYPE_DISCONNECT:
        print("Disconnecting")
        connected = False
