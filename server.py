import socket
import sys
import threading
import select
import random
import Queue
from check import ip_checksum

class Game():
	def __init__(self, name, tries):
		self.name = name
		self.max_tries = tries
		self.players = []
		self.word = 'null'
		self.letter_correct = []

		self.turn = 0

		self.guessed_letters = []

		self.cmd_q = Queue.Queue()
		self.done_running = False
	
		self.ongoing = True
		self.s = None

	def get_player(self, query): # returns list so you can test for bool too
		return [x for x in self.players if (x.addr == query) or (x.name == query)]

	def add_player(self, client):
		self.cmd_q.put('notify\n'+client.name+' has joined the game!')
		self.players.append(client)
		client.lives = self.max_tries
		self.cmd_q.put('update')
	
	def expel(self, uname):
		player = self.get_player(uname)[0]
		player.clear()
		player.send_pkt(self.s, 'lose')
		self.players.remove(player)
		self.cmd_q.put('notify\n'+uname+' has been executed. The crowd is pleased.')

	def set_word(self, word):
		self.word = word
		self.letter_correct = []
		for letter in word:
			self.letter_correct.append(False)

	def progress(self):
		if self.turn+1 >= len(self.players) : self.turn = 0
		else : self.turn += 1

	def return_status(self): # Returns current game status in string format
		fragment = 'Word - '
		for i in range(0, len(self.word)):
			if self.letter_correct[i] : fragment = fragment + self.word[i]
			else : fragment = fragment + '_'
		glist = 'Guessed Letters : ' + ' '.join(self.guessed_letters)
		pl_str = ''
		for player in self.players:
			pl_str = pl_str + player.name + ' (' + str(player.lives) + ') ' + str(player.score)
			if player == self.players[self.turn] : pl_str = pl_str + ' *'
			pl_str = pl_str + '\n'
		return fragment+'\n'+glist+'\n'+pl_str

	def notify(self, msg) :
		msg = "broadcast\nGAME: " + msg
		for player in self.players:
			player.send_pkt(self.s, msg)

	def send_update(self):
		pkt = 'update\n'
		pkt += '-----Game Board-----\n'+self.return_status()+'--------------------'+'\n'
		for player in self.players:
			player.send_pkt(self.s, pkt)

	def chat_msg(self, sender, msg): # sender is just the uname string
		pkt = 'chat\n'+sender+'\n: '+msg
		for player in self.players: # Send actual message to all players
			player.send_pkt(self.s, pkt)
		if msg[0] == '!': # is a command
			#print 'Command recognized'
			args = msg.split()
			if args[0] == '!guess' and sender == self.players[self.turn].name: # Guess letter
				if not args[1]: return
				self.guess(sender, args[1])	
			elif args[0] == '!redisplay': # Redisplay hangman ui
				self.cmd_q.put('update')
			elif args[0] == '!guess_word': # Guess entire word
				if not args[1]: return
				pkt = 'notify\n' + sender + ' guessed the word was ' + args[1]
				if args[1] == self.word: 
					pkt += '... and they are correct!'
					self.cmd_q.put(pkt)
					self.get_player(sender)[0].score += len(self.word)
					self.cmd_q.put('conclude')
				else: 
					pkt += '... and they are wrong! See you in hell!'
					self.cmd_q.put(pkt)
					self.cmd_q.put('expel\n'+sender)
					self.cmd_q.put('update')

	def guess(self, uname, letter):
		#print 'Attempting to guess letter...'
		player = self.get_player(uname)[0];
		if letter in self.guessed_letters:
			self.cmd_q.put('notify\nLetter already has been guessed. Try again.')
			return
		flag = False
		# Probably a better pythonic way to do this
		# Only one turn, display menu after this
		for i in range(0, len(self.word)):
			if self.word[i] == letter: 
				self.letter_correct[i] = True
				player.score += 1
				flag = True
		if all(right for right in self.letter_correct) : self.conclude()
		else :
			if not flag : # They got it wrong
				player.lives -= 1
				if player.lives <= 0: self.expel(uname)
				self.progress()
			self.guessed_letters.append(letter)
			self.cmd_q.put('update')
		return

	def conclude(self): # Calculates scores, announces winners, closes game
		#print 'Game is over! Calculating scores...'
		# Calculate scores
		winners = [] # empty list
		losers = self.players[:] # full list
		max_score = -1
		for player in self.players :
			#print player.name + "'s score: " + str(player.score)
			if player.score > max_score:
				losers.extend(winners)
				losers.remove(player)
				winners = [player]
				max_score = player.score
			elif player.score == max_score:
				losers.remove(player)
				winners.append(player)
		# Send win code to winner, all else loser
		for player in winners:
			#print player
			player.clear()
			player.send_pkt(self.s, 'win')
		for player in losers:
			player.clear()
			player.send_pkt(self.s, 'lose')

		self.ongoing = False
		
	def tick(self): # This is where the next queue command is parsed
		# Everything is done in a queue to make sure it happens in the right order
		if not self.cmd_q.empty():
			cmd = self.cmd_q.get(False).splitlines()
			if cmd[0] == 'notify':
				self.notify(cmd[1])
			elif cmd[0] == 'chat': # code, sender, message
				self.chat_msg(cmd[1], cmd[2])
			elif cmd[0] == 'update':
				del cmd[0]
				self.send_update()
			elif cmd[0] == 'expel':
				self.expel(cmd[1])
			elif cmd[0] == 'conclude':
				self.conclude()
			self.done_running = True
		elif self.done_running and self.cmd_q.empty():
			for player in self.players: player.send_pkt(self.s, 'reinput')
			self.done_running = False

class Client():
	def __init__(self, name, addr):
		# Not gonna do ACKs here. Unreliable one-way packets
		self.name = name
		self.addr = addr

		self.score = 0
		self.lives = 0

	def clear(self):
		self.score = 0
		self.lives = 0

	def send_pkt(self, s, pkt):
		#print 'Sending to ' + self.name + '@' + self.addr[0] + ':' + str(self.addr[1])
		s.sendto(pkt, self.addr)

	def __eq__(self, other):
		if isinstance(self, other.__class__):
			return self.addr == other.addr
		return False

class Database():
	hall_of_fame = ['Guy1', 'Dude', 'Guy3', 'Who?', 'Hello World']
	ongoing_games = []
	word_list = ['networks', 'routing', 'engineering']
	users = {'admin':'pass', 'user':'dude'}
	clients = []	

	def get_client(self, query): # returns list so you can test for bool too
		return [x for x in self.clients if (x.addr == query) or (x.name == query)]

	def get_game(self, query):
		return [x for x in self.ongoing_games if (query == x.name) or (query in x.players)]

class TransportLayer(threading.Thread):
	def __init__(self, data_q, reply_q):
		super(TransportLayer, self).__init__();
		
		self.HOST = ''	#Symbolic name meaning all available interfaces
		self.PORT = 8000 #Arbitrary non-priveliged port

		self.source = [] # This dynamically changes with every packet recieved

		self.data_q = data_q
		self.reply_q = reply_q
		self.stop_request = threading.Event()

		self.data = "";
		self.reply = None;

		self.db = Database()

		random.seed()

		try:
			self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			print 'Socket created'
		except socket.error, msg:
			print 'Failed to create socket. Error code: ' + str(msg[0]) + \
			' Message ' + msg[1]
			sys.exit()

		# Socket binding
		try:
			self.s.bind((self.HOST, self.PORT))
		except socket.error, msg:
			print 'Bind failed. Error Code: ' + str(msg[0]) + ' Message ' \
			+ msg[1]
			sys.exit()
			
		self.s.setblocking(0)

		print 'Socket bind complete'

	def route_msg(self, msg):
		# Here we have a list of codes from the client
		# Fill self.data with appropriate data to send to or back
		# Other codes will have it just print received data
		msg = msg.splitlines();
		#print msg
		if (msg[0] == 'hall_of_fame'):
			for hero in self.db.hall_of_fame:
				self.data = self.data + hero + '\n'

		elif (msg[0] == 'words'):
			for word in self.db.word_list:
				self.data = self.data + word + '\n'
			self.reply_q.put(self.data)
			return

		elif (msg[0] == 'add_word'): # code, new word
			self.db.word_list.append(msg[1])
			self.reply_q.put('added')
			return

		elif (msg[0] == 'login'): # code, user,  pass
			if (msg[1] in self.db.users):
				# checks for valid pass and not already logged in
				self.data = (self.db.users[msg[1]] == msg[2]) and not self.db.get_client(msg[1])				
				if self.data:
					#print 'New Client Recorded'
					self.db.clients.append(Client(msg[1], self.addr))
					#print self.db.clients
				
		elif (msg[0] == 'make_user'):
			if (msg[1] not in self.db.users):
				self.db.users[msg[1]] = msg[2]
				self.data = True
			else: self.data = False

		elif (msg[0] == 'get_games'):
			for game in self.db.ongoing_games:
				self.data = self.data + game.name + '\n'

		elif (msg[0] == 'exit'):
			c = self.db.get_client(self.addr)
			if c:
				self.db.clients.remove(c[0])
			#print self.db.clients
			self.data = 'confirm'

		elif (msg[0] == 'players'):
			for player in self.db.clients:
				self.data += player.name + '\n' 
			self.reply_q.put(self.data)

		elif (msg[0] == 'broadcast'):
			# Get all current clients, send to all
			self.reply = 'broadcast\nSERVER: ' + msg[1] + '\n'
			for client in self.db.clients :
				client.send_pkt(self.s, self.reply)
			self.reply_q.put('success') # Unlock parent thread
			return True
				
		elif (msg[0] == 'chat'):
			# Append with client name, send to all
			sender = self.db.get_client(self.addr)[0]
			game = self.db.get_game(sender)[0]
			#print 'Received chat message from ' + sender.name
			game.cmd_q.put('chat\n'+sender.name+'\n'+msg[1])
			self.data = 'True' # Msg sent corrently?

		elif (msg[0] == 'new_game'):
			game = Game(msg[2], int(msg[1]))
			self.db.ongoing_games.append(game)
			c = self.db.get_client(self.addr)[0]
			game.s = self.s # Work around for non-global socket
			game.set_word(self.db.word_list[random.randint(0,len(self.db.word_list)-1)]) # Set this to a random entry later
			game.add_player(c)
			# game.cmd_q.put('update\nYour Word - ' + game.word)
			self.data = 'True' # Game started correctly

		elif (msg[0] == 'join_game'): # code, game index
			if int(msg[1]) > len(self.db.ongoing_games):
				self.data = 'False'
				return
			game = self.db.ongoing_games[int(msg[1])-1]
			c = self.db.get_client(self.addr)[0]
			game.add_player(c)
			self.data = 'True'

		else: print 'Invalid control code'

		return False

	def tick(self):
		# Progress all games
		for game in self.db.ongoing_games:
			if game.ongoing : game.tick()
			else : self.db.ongoing_games.remove(game)

		#Receive data from client.
		readable, writable, exceptional = select.select([self.s], [], [], 0);
		d = None
		self.data = ""
		self.reply = ""
		if readable:
			d = self.s.recvfrom(1024)
			data = d[0]
			self.addr = d[1]
			self.source = str(d[1])
			# print 'Handled player request'
		elif not self.data_q.empty():
			d = self.data_q.get(False)
			# print 'Host packet contents : ' + d
			self.route_msg(d)
			return
		else: return

		# Take apart packet
		self.ack = data[4]
		msg = data[5:-2]
		chksum = data[-2:]
		
		'''
		print 'OK... \n' + \
		'Source Port : ' + self.source + '\n' \
		'Ack : ' + self.ack + '\n' + \
		'Data : ' + msg + '\n'# + \
		# 'Checksum : [' + chksum + ']';
		'''

		# print 'This checksum : [' + ip_checksum(msg) + ']'
		if ip_checksum(msg) == chksum: # Not corrupt
			# print 'Routing message to correct control code.'
			self.route_msg(msg)
			self.ack = '0' if (self.ack == '0') else '1'
		else:
			self.ack = '1' if (self.ack == '1') else '0'
		
		#print 'Denying packet for 7.5 seconds...'
		#time.sleep(7.5);
		
		reply = 'ACK' + self.ack + '\n' + str(self.data);
		# print 'Sending reply : ' + reply 
		
		self.s.sendto(reply, (self.addr[0], self.addr[1]));
		# print 'Message[' + self.addr[0] + ':' + str(self.addr[1]) + '] - ' + data.strip();
		# Reinit console input
		#sys.stdout.write('> User Input: ')
		#sys.stdout.flush()

	def run(self):
		while not self.stop_request.isSet():
			self.tick()
		s.close()
	
	def join(self, timeout=None):
		self.stop_request.set()
		super(TransportLayer, self).join(timeout)

