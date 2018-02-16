#Socket client for python

import socket # socket library
import sys # for exit handling
import threading # for starting transport layer thread
from client import TransportLayer
import Queue

main = ['-Main Menu-', '1. Login', '2. Make New User', '3. Hall of Fame', '4. Exit'];
game = ['-Game Menu-', '1. Start New Game', '2. Get List of Games', '3. Hall of Fame', '4. Exit'];
level = ['Choose Difficulty:', '1. Easy', '2. Medium', '3. Hard'];

data_q = Queue.Queue()
reply_q = Queue.Queue()

def init():
	
	global data_q
	global reply_q
	global uname
	global client
	
	# Create new thread of udt_sm?
	client = TransportLayer(data_q, reply_q)
	client.setName('Transport Layer')
	client.daemon = True
	client.start()
	
def line():
	print '####################'

def request_server(request, send_data):
	# Send to transport layer
	# All of these should have blocking calls to synchronize parent and child.
	if request == 'hall_of_fame' or request == 'get_games':
		data_q.put(request)
		return reply_q.get(True, 5).splitlines()
	elif request == 'login' or request == 'make_user':
		pkt = request+'\n'+send_data[0]+'\n'+send_data[1]
		data_q.put(pkt)
		return reply_q.get(True, 5) == "True"
	elif request == 'chat':
		pkt = request+'\n'+send_data
		data_q.put(pkt)
		return
	elif request == 'new_game':
		pkt = request+'\n'+str(send_data[0])+'\n'+send_data[1]
		data_q.put(pkt)
		return reply_q.get(True, 5) == "True"
	elif request == 'join_game':
		pkt = request+'\n'+send_data[0]
		data_q.put(pkt)
		return reply_q.get(True, 5) == "True"
	return

def display_menu(lines):
	for line in lines:
		print line
	reply = raw_input('> User Input: ')
	return int(reply) if (reply.isdigit()) else int('-1')

def login(): 
	user = raw_input('> Enter your Username : ');
	passwd = raw_input('> Enter your Password : ');
	#Send to server, see if is in database, should get back a bool from server
	valid = request_server('login', [user, passwd]);
	if valid:
		data_q.put('PARENT\n'+user) # Send uname to child thread
		reply_q.get(True,5) # Semaphore blocking call
		print 'Successfully logged in.'
		return user
	else:
		print 'Invalid Username or Password, or User is already logged in'
	return ""
	 
def make_user():
	user = raw_input('> Enter your desired Username : ')
	passwd = raw_input('> Enter your desired Password : ')
	#Send to server, see if taken/valid. register on server side
	valid = request_server('make_user', [user, passwd])
	if valid:
		print 'User successfully created.'
	else:
		print 'Username already taken or invalid inputs.'
	
def hall_of_fame():
	#Request hall of fame from server
	players = request_server('hall_of_fame', None)
	#Have server return the top scorers
	print '@ Hall of Fame @'
	for player in players:
		print '* ' + player
	
def safe_exit():
	print 'See you later!'
	if uname : 
		data_q.put('exit'+'\n'+uname)
		reply_q.get(True, 5)
	#s.close()
	data_q.put(None)
	sys.exit()
	
def start_game():
	difficulty = -1
	while difficulty <= 0 or difficulty >= 4:
		difficulty = display_menu(level)
		if difficulty <= 0 or difficulty >= 4: print 'Enter a valid difficulty'
	settings = [9/difficulty, raw_input('> Game Display Name: ')]
	# Send signal to start new game to server
	reply = request_server('new_game', settings)

	print 'The game has begun!'
	play_game()

	# Game finished or you lose prematurely
	return

def get_games():
	#Request games from server
	#Have server return games
	games = request_server('get_games', None)
	print '@ Currently Running Games @'
	if not games: 
		print 'No currently ongoing games.'
		return
	i=1 # Very very shoddy design
	for game in games:
		print str(i) + '. ' + game
		i=i+1

	reply = raw_input('> Game to join (0 for none): ')
	if reply == '0': return
	elif request_server('join_game', reply):
		print 'Welcome to the game in progress!'
		play_game()
	else:
		print 'Game #' + reply + ' does not exist'
	
def play_game():
	data_q.put('PLAYING\nTrue') # Let client know we are playing
	reply_q.get(True, 5)
	
	print 'You can chat simply by entering text.'
	print 'When it\'s your turn, enter one of the commands for your action.'
	print '  !guess [letter]    - Guesses a letter'
	print '  !redisplay         - Redisplays the hangman UI'
	print '  !guess_word [word] - Guess the whole word. You are expelled if it\'s wrong.'

	game_over = False	

	# Begin sending replies to the server
	sys.stdout.write('> Chat: ')
	sys.stdout.flush()
	while not game_over:
		reply = raw_input()	
		if reply : request_server('chat', reply)

		while not reply_q.empty():
			reply = reply_q.get(False, 5)
			if reply == 'win' or reply == 'lose' : game_over = True
			
	data_q.put('PLAYING\nFalse') # Let client know we have ended
	reply_q.get(True, 5)
# -------------------------------------------------------------------- #

init();

line();
print 'Welcome to the bastardized version of hangman!'

uname = ""

while 1:
	line()
	if not uname: reply = display_menu(main) 
	else: reply = display_menu(game)
	
	if reply == 1:
		if not uname: uname = login()
		else: start_game()
	elif reply == 2:
		if not uname: make_user()
		else: get_games()
	elif reply == 3:
		hall_of_fame()
	elif reply == 4:
		safe_exit()
	else:
		print "Invalid command entered."
