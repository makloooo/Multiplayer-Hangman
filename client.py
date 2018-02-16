#Socket client for python

import socket # socket library
import sys # for exit handling
import threading
import random
import select
from check import ip_checksum

class TransportLayer(threading.Thread):
	def __init__(self, data_q, reply_q):
		super(TransportLayer, self).__init__()
		self.data_q = data_q # Receive Queue
		self.reply_q = reply_q # Send Queue
		self.stop_request = threading.Event()
		
		# Only players need their own port number
		random.seed(None)
		self.host = ''
		self.port = random.randint(7000,7500)
		
		self.playing = False
		self.parent = ''
		
		self.destport = 8000
		
		self.data = None; # Data received
		self.reply = None; # Data to send
		
		self.t = None;
		
		self.state = 0;
		
		try:
			# Create a IPv4 UDP socket in python
			self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM);
		except socket.error, msg:
			print 'Failed to create socket. Error code: ' + str(msg[0]) \
			+ ' , Error message : ' + msg[1]
			sys.exit();

		print 'Socket Created'

		try:
			remote_ip = socket.gethostbyname(self.host)
		except socket.gaierror:
			# could not resolve
			print 'Hostname could not be resolved. Exiting.'
			sys.exit();

		print 'Socket Connected to ' + self.host + ' on ip ' + remote_ip
		
	def poll_data(self):			
		# Check from server or client
		readable, writable, exceptional = select.select([self.s], [], [], 0);
		if readable: # Process here
			self.data = self.s.recvfrom(1024)[0] # Unreliable one-way packets. no ACK
			#print '\nReceived server packet : ' + str(self.data)
			self.process_pkt()
			return False # Not really, just have no reason to progress SM
		elif not self.data_q.empty(): 
			self.data = self.data_q.get(False)
			#print 'Client packet contents : ' + str(self.data)
			if self.data.splitlines()[0].isupper(): 
				self.process_pkt()
				return False # For client use only, don't send
			return True # Send to server
		return False

	def process_pkt(self):
		msg = self.data.splitlines() # Splits up the packet into args
		self.reply = self.data
		#print msg
		if not msg : 
			self.reply = ''
		elif msg[0] == 'broadcast': # Sent from server, print to everyone
			print '\n' + msg[1]
			return
		elif msg[0] == 'chat': # Sent from user
			# if sender is themselves, dont print newline, since already echoed
			if not msg[1] == self.parent: print ''
			sys.stdout.write(msg[1] + msg[2] + ' | ')
			sys.stdout.flush()
			return
		elif msg[0] == 'update':
			del msg[0]
			print ''
			for line in msg: print line
			return
		elif msg[0] == 'reinput':
			if self.playing: sys.stdout.write('> Chat: ')
			else: sys.stdout.write('> User Input: ')
			sys.stdout.flush()
		elif msg[0] == 'lose':
			print '\nIt\'s over for you! Better luck next time sucker!'
			print 'Press Enter to Escape the void back to the Main Menu'
			self.reply = msg[0]
		elif msg[0] == 'win':
			print '\nCongratulations, you won!\nPress Enter to return to the Main Menu'
			self.reply = msg[0]
		# Uppercase for client use only, these are mainly for output formatting
		elif msg[0] == 'PARENT': 
			self.parent = msg[1]
			self.reply = True
		elif msg[0] == 'PLAYING':
			self.playing = (str(msg[1]) == "True")
			self.reply = str(self.playing)
		#print 'Sending up : ' + str(self.reply)
		self.reply_q.put(self.reply)
		return

	def make_pkt(self, flag, chksum):
		# Lets just send it as a string
		packet = str(self.port) + str(flag) + self.data + chksum;
		#print 'Packet Contents : ' + packet
		return packet

	def isACK(self, flag):
		return self.rcvpkt[3] == str(flag)

	def corrupt(self):
		return not (self.rcvpkt[0:3] == "ACK");

	def udt_send(self, flag):
		checksum = ip_checksum(self.data);
		sndpkt = self.make_pkt(flag, checksum);
		self.s.sendto(sndpkt, (self.host, self.destport));

	def tick(self):
		
		# State actions
		if self.state == 0: # Wait on the master application
			# Parent thread is your master application
			if not self.poll_data() : return

			# Wait on event from parent thread
			if self.data == None:
				self.s.close();
				sys.exit();
			
		elif self.state == 1: # Wait for ACK0
			# This blocks the system for you, so you won't continue until 
			# you receive a packet from the server
			#print 'Waiting on packet with ACK0...'
			
			self.rcvpkt = self.s.recv(1024);
			
		elif self.state == 2: # Wait on the master application (the console)
			# Wait on event from parent thread
			if not self.poll_data() : return

			if self.data == None:
				self.s.close();
				sys.exit();
			
		elif self.state == 3: # Wait on ACK1
			#print 'Waiting on packet with ACK1...'
			self.rcvpkt = self.s.recv(1024);
			
		# Transitions
		if self.state == 0: # Send data
			# Once you get data, make packet, send packet, create thread
			self.udt_send(0);
			# Start timer here
			self.t = threading.Timer(5.0, self.udt_send, [0]);
			self.t.start();
			
			self.state = 1;
			
		elif self.state == 1: # Check for packet integrity from server
			if (not self.corrupt() and self.isACK(0)):
				#print 'Packet recieved!'
				#print 'Server Reply : ' + self.rcvpkt;
				self.t.cancel(); # Stop timer here
				self.data = self.rcvpkt[5:] # Get rid of the ACK
				self.process_pkt();
				self.state = 2;
			elif (self.corrupt() or self.isACK(1)):
				print 'Corrupt or duplicate packet received'
				print 'Server Reply : ' + self.rcvpkt;
		
		elif self.state == 2: # Send data
			# Once you get data, make packet, send packet, create thread
			self.udt_send(1);
			# Start timer here again
			self.t = threading.Timer(5.0, self.udt_send, [1]);
			self.t.start();
			
			self.state = 3;
			
		elif self.state == 3: # Check for packet integrity from server
			if (not self.corrupt() and self.isACK(1)):
				#print 'Packet recieved!'
				#print 'Server Reply : ' + self.rcvpkt;
				self.t.cancel(); # Stop timer here 
				self.data = self.rcvpkt[5:]
				self.process_pkt()
				self.state = 0;
			elif (self.corrupt() or self.isACK(0)):
				print 'Corrupted or duplicate packet received'
				print 'Server Reply : ' + self.rcvpkt;
			
	def run(self):
		# Keep on running until terminated by the player process
		# Continue receiving data from player and sending it to 
		# the server using the rdt send process.
		while not self.stop_request.isSet():
			self.tick()
		s.close()
		
	def join(self, timeout=None):
		self.stop_request.set()
		super(TransportLayer, self).join(timeout)
		
