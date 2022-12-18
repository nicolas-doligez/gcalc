#!/usr/bin/env -S PATH=/usr/local/bin:${PATH} python3

#we use env shebang in order to launch from linux and MacOS
#MacOS installs python3 in /use/local/bin
#linux installs python3 in /usr/bin (included in default PATH)

#author : Julie Doligez  doligez.julie@gmail.com
#this was written during my intership in Barcelona september-december 2022
#if you use or modify this code, please let me know :)

import sys
import os
import pathlib
import socket
import webbrowser

#add the current dir to the import search path
#needed to launch from the project script
#alternate mathod is : from .util import *
#but this breaks the ability to launch directly gaiacalc.py during dev
#include this inside the code and not in __init__.py
#because we need it also in bundled exe file built by pyinstaller
sys.path.append(os.path.dirname(__file__))

from util import *
from loop import *
from index import *
from webserver import *
from show import *

lastone = None #last point displayed in hover() callback

def pidfile():
	
	#the pidfile contains the process number for linux platform
	#used by the daemon launcher /etc/init.d/gaiacalc to stop the server properly
	#we try to write the pidfile and ignore any failure
	#if the current user is not root, no pid file will be set
	#but this also means that the webserver is not a regular linux daemon
	#(and it will run on TCP port 8080, not the default HTTP port 80)

	if sys.platform == 'linux':
		try:
			with open('/var/run/gaiacalc.pid', 'w') as f:
				f.write(str(os.getpid()))
		except: pass


def checkargs():
	"""log and check arguments"""

	#log command path and arguments
	log(f'starting ')
	for a in sys.argv:
		log(f'{a} ')
	log('\n')
	log(f'input is {args.inputfile.name}\n')
	log(f'output is {args.output or "<stdout>"}\n')
	log(f'error is {args.log.name}\n')

	#convert tab separator for TAB character
	args.separator = '\t' if args.separator == '\\t' else args.separator

	#check dir option
	if not args.data.is_dir():
		log("wrong data directory option\n")
		parser.print_help()
		exit()

	#check for curves directories
	if not DA.path.is_dir() and DB.path.is_dir():
		log("missing directory for DA and/or DB\n")
		parser.print_help()
		exit()

	#check format for stdout
	if args.format == 'bin' and args.output == None:
		log('cannot write binary to stdout\n')
		parser.print_help()
		exit()

def mainproc():
	pidfile()
	checkargs()
	initgrids()
	
	if args.exec:
		#exec from shell command (no webserver launching)
		samples = mainloop()
		
		if args.show:
			#prepare figures with curves, grid and samples
			showwindows(samples)
			
			#both figures are ready
			#now diplay both windows and listen for mouve events on active window
			#code will exit when the user closes both DA/DB windows (no exit button on screen)
			#this will block for event loop
			plot.show()

	else:
		#webserver mode
		
		#only use matplotlib to generate data in a file
		#no need to manage windows on screen for webserver mode
		#see https://stackoverflow.com/a/66567690
		plot.switch_backend('Agg')

		host = '127.0.0.1'
		if args.public:
			#first extract server IP address
			#see https://stackoverflow.com/a/28950776
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.settimeout(0)
			try:
				# doesn't even have to be reachable
				s.connect(('10.254.254.254', 1))
				host = s.getsockname()[0]
			except: pass
			finally:
				s.close()

		log('opening webserver host %s port %d\n' % (host,args.tcpport))
		cherrypy.server.socket_host = host
		cherrypy.server.socket_port = args.tcpport
		cherrypy.log.screen = False
		cherrypy.log.access_file = str(topdir/'log/access.log')
		cherrypy.log.error_file =str(topdir/'log/error.log')

		#launch safari and load the main web page
		#this will have no effect on linux server with no window manager
		#server is launched below but will answer to the browser request
		webbrowser.open(f'http://{host}:{args.tcpport}')
		
		#launch webserver : this will block forever
		cherrypy.quickstart(webserver())
    

def subproc():
	#this is done only in subprocesses
	#each subprocess loads the same source file as the main process
	#we need to build the geometrical index in each subprocess
	#to be able to interpolate points dispatched by the main process

	for data in (DA,DB):
		indexcurves(data)
	log("subprocess ready at time %f\n" % time.time())


if __name__ == '__main__':
	#we are in the process launched from shell
	mainproc()
else:
	#we are in a subprocess launched by the main process
	subproc()
