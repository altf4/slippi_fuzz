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
    def __init__(self, frame):
        self.messageId = 0x80
        self.frame = frame
        self.playerIdx = 0x00
        # Then contains N pads (each 8 bytes)
        if self.frame < 200:
            # Neutral
            self.pads = [0x0000007F7F7F0000]
        else:
            # Dash dance
            if self.frame % 2:
                print("left")
                self.pads = [0x0000607F7F7F0000]
            else:
                print("right")
                self.pads = [0x00009F7F7F7F0000]

    def to_buffer(self):
        paramlist = []
        paramlist.append((self.messageId).to_bytes(1, byteorder='big'))
        paramlist.append((self.frame).to_bytes(4, byteorder='big', signed=True))
        paramlist.append((self.playerIdx).to_bytes(1, byteorder='big'))
        for pad in self.pads:
            paramlist.append((pad).to_bytes(8, byteorder='big'))
        return b"".join(paramlist)

class PadAck:
    def __init__(self):
        self.messageId = 0x81
        self.frame = 0x00000000
        self.playerIdx = 0x00

    def to_buffer(self):
        paramlist = []
        paramlist.append((self.messageId).to_bytes(1, byteorder='big'))
        paramlist.append((self.frame).to_bytes(4, byteorder='big', signed=True))
        paramlist.append((self.playerIdx).to_bytes(1, byteorder='big'))
        return b"".join(paramlist)

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
    """Currently unused by Slippi, but it's a valid message type that DOES get read"""
    def __init__(self):
        self.messageId = 0x83
        # No other fields

    def to_buffer(self):
        paramlist = []
        paramlist.append((self.messageId).to_bytes(1, byteorder='big'))
        return b"".join(paramlist)

class ChatMessage:
    def __init__(self):
        self.messageId = 0x84
        self.chatMessage = 0x00000000
        self.playerIdx = 0x00

    def randomize(self):
        self.messageId = 0x84
        # Anything other than the enumerated values are rejected as of PR-290
        #   so don't bother fuzzing random values for the chat message ID
        # self.chatMessage = random.getrandbits(32)
        self.chatMessage = random.choice([136,129,130,132,34,40,33,36,72,66,68,65,24,18,20,17])
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
    request["appVersion"] = "2.3.3"
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
while True:
    event = host.service(2000)
    if event.type == enet.EVENT_TYPE_NONE:
        print("Reaching out to opponent...")
        pass
    elif event.type == enet.EVENT_TYPE_RECEIVE:
        pass
    elif event.type == enet.EVENT_TYPE_CONNECT:
        print("Connected to opponent!")
        break
    elif event.type == enet.EVENT_TYPE_DISCONNECT:
        print("Disconnecting")
        sys.exit(1)

# We are finally connected to our opponent.
# Now we get to the actual fuzzing.
print("Fuzzing will now start!")

###### STEP ONE: Chat messages at CSS #######
#   1000 randomized chat messages fast
print("Step One: Chat messages")
sent_messages = 0
while sent_messages < 10000:
    chat = ChatMessage()
    chat.randomize()
    peer.send(0, enet.Packet(chat.to_buffer()))
    sent_messages += 1

    event = host.service(50)
    if event.type == enet.EVENT_TYPE_NONE:
        pass
    elif event.type == enet.EVENT_TYPE_RECEIVE:
        pass
    elif event.type == enet.EVENT_TYPE_CONNECT:
        break
    elif event.type == enet.EVENT_TYPE_DISCONNECT:
        print("Disconnecting")
        sys.exit(1)

###### STEP TWO: Out of order messages during game #######
# Send some normal selections, to start the game
print("Step Two: In-game")
selections = PlayerSelections()
peer.send(0, enet.Packet(selections.to_buffer()))

previous_time = time.time() * 1000

current_frame = -123
start_pads = False
while True:

    # Send the pad if it's time
    current_time = time.time() * 1000
    if abs(previous_time - current_time) > 16.6666 and start_pads:
        pad = Pad(current_frame)
        print("Sending pad frame", current_frame)
        current_frame += 1
        peer.send(0, enet.Packet(pad.to_buffer()))
        previous_time = current_time

    event = host.service(5)
    if event.type == enet.EVENT_TYPE_NONE:
        pass
    elif event.type == enet.EVENT_TYPE_RECEIVE:
        messageId = int.from_bytes(event.packet.data[0:1], byteorder='big', signed=False)
        print("Got message with ID: ", messageId)
        print("\npayload:", event.packet.data)
        # Pad
        if messageId == 0x80:
            # We need to ack pads that come in. Do that here
            frame = int.from_bytes(event.packet.data[1:5], byteorder='big', signed=True)
            pad_ack = PadAck()
            pad_ack.frame = frame
            print("Got pad for: ", frame)
            peer.send(0, enet.Packet(pad_ack.to_buffer()))
            start_pads = True
        # PlayerSelections
        if messageId == 0x82:
            pad = Pad(-123)
            print("Sending pad frame", current_frame)
            current_frame += 1
            peer.send(0, enet.Packet(pad.to_buffer()))
            previous_time = current_time
            start_pads = True

    elif event.type == enet.EVENT_TYPE_CONNECT:
        break
    elif event.type == enet.EVENT_TYPE_DISCONNECT:
        print("Disconnecting")
        sys.exit(1)
