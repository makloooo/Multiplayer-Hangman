from server import TransportLayer
import Queue
import sys

data_q = Queue.Queue()
reply_q = Queue.Queue()

main_menu = ['1. Current List of Users', '2. Current List of Words', '3. Add New Word to List of Words', '4. Broadcast message', '5. Shut Down']

def line():
	print '####################'

def init():
	global data_q
	global reply_q
	global server
	
	# Create new thread of udt_sm?
	server = TransportLayer(data_q, reply_q)
	server.setName('Transport Layer')
	server.daemon = True
	server.start()
	
def display_menu(lines):
	for line in lines:
		print line
	reply = raw_input('> User Input: ')
	return int(reply) if (reply.isdigit()) else int('-1')
	
def display_users():
	data_q.put('players')
	users = reply_q.get(True, 5).splitlines()
	if not users:
		print 'There are currently no users playing'
	else:
		print '# List of Users Playing #'
		for user in users:
			print '* ' + user
	
def display_words():
	data_q.put('words')
	word_list = reply_q.get(True, 5).splitlines()
	print '# List of Words in Play #'
	for word in word_list:
		print '* ' + word
		
def add_word():
	data_q.put('add_word'+'\n'+(raw_input('> New Word to Add : ')))
	reply_q.get(True, 5) # Wait until done adding
	
def broadcast_msg():
	msg = 'broadcast\n'
	msg += raw_input('> Message to Broadcast : ')
	data_q.put(msg)
	reply_q.get(True, 5) # Acts as a semaphore for the transport layer

def safe_exit():
	print 'See you later!'
	#s.close()
	data_q.put(None)
	sys.exit()
# -------------------------------------------------------------------- #

init()

while 1:
	line()
	reply = display_menu(main_menu)
	
	# Update users in game
	
	if reply == 1:
		display_users()
	elif reply == 2:
		display_words()
	elif reply == 3:
		add_word()
	elif reply == 4:
		broadcast_msg()
	elif reply == 5:
		safe_exit()
	else:
		print "Invalid command entered."

print 'Server running'
