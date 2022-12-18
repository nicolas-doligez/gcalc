import sys
import os
import re
import datetime
import time
import pathlib
import argparse
import rtree

topdir = pathlib.Path(__file__).parent

#arguments parser
parser = argparse.ArgumentParser()

parser.add_argument('inputfile', nargs='?', type=argparse.FileType('r', encoding='utf-8-sig'), default=sys.stdin, help='input file')
parser.add_argument('--header', action='store_true', help='use header line for column names')
parser.add_argument('--bprp', action='store', default='bprp', help='bprp column name in csv input file')
parser.add_argument('--gabs', action='store', default='gabs', help='gabs column name in csv input file')
parser.add_argument('--prob', action='store', default='prob', help='probability column name in csv input file')
parser.add_argument('--no-prob', action='store_true', help='compute both DA and DB to find mean mass/temp')
parser.add_argument('-f', '--force', action='store_true', help='force geometric indexing')
parser.add_argument('-s', '--show', action='store_true', help='show results in graphical windows on screen')
parser.add_argument('-o', '--output', metavar="FILE", help='output file')
parser.add_argument('-d', '--data', default=topdir/'data', type=pathlib.Path, help='dir for data files')
parser.add_argument('--csv', action='store_const', dest='format', default='csv', const='csv', help='csv output')
parser.add_argument('--bin', action='store_const', dest='format', const='bin', help='binary output')
parser.add_argument('--max-bprp', action='store', type=float, help='max bprp input filter')
parser.add_argument('--min-bprp', action='store', type=float, help='min bprp input filter')
parser.add_argument('--max-gabs', action='store', type=float, help='max gabs input filter')
parser.add_argument('--min-gabs', action='store', type=float, help='min gabs input filter')
parser.add_argument('--debug', action='store_true', help='generate debug files')
parser.add_argument('-l', '--log', action='store', type=argparse.FileType('a'), default=sys.stderr, help='log file name')
parser.add_argument('-p', '--perf', action='store_true', help='toggle performance logging')
parser.add_argument('-e', '--exec', action='store_true', help='command line mode')
parser.add_argument('--public', action='store_true', help='webserver available worldwide')
parser.add_argument('--tcpport', action='store', type=int, default=8080, help='webserver port')
parser.add_argument('--separator', action='store', default=';', help='CSV separator')
parser.add_argument('--decimal', action='store', default='.', help='decimal separator')
parser.add_argument('-g', '--grid', action='store', type=int, default=200, help='grid index size')

#args = parser.parse_args([x for x in sys.argv if not re.search('=',x) and not re.search('fork',x)][1:])
args = parser.parse_args()


#define all exceptions we need
class EndOfCurveException(Exception): pass
class AboveFlagException(Exception): pass
class BelowFirstCurveException(Exception): pass
class AboveLastCurveException(Exception): pass
class CrossingCurvesException(Exception): pass
class ColumnsException(Exception): pass


logtime = False #True when logtime has been included at beginning of line
def log(message):
	#you should take care that any log line includes terminating \n
	global logtime
	if not logtime:
		message = (str(datetime.datetime.now()) + ' ') + message
	logtime = message[-1] != '\n' #reset logtime for next line
	args.log.write(message) #write in log file or defaults to stderr
	args.log.flush() #flush immediately
	return True #useful to log inside boolean expression


class performance:
	#this is a tool to generate performance logs on screen
	#usage : with performance("text message"):
	def __init__(self, msg, howmany=None):
		self.msg = msg
		self.howmany = howmany
	def __enter__(self):
		self.since = time.time()
		if args.perf:
			log('starting %s at %f\n' % (self.msg, self.since))
		else:
			log(self.msg + '\n')
		return self
	def __exit__(self, type, val, tb):
		if args.perf:
			until = time.time()
			log('done %s at %f\n' % (self.msg, until))
			log('---- %s duration = %f\n' % (self.msg, until - self.since))
			if self.howmany:
				log('---- %s %d items\n' % (self.msg, self.howmany))
				log('---- %s rate = %d/s\n' % (self.msg, self.howmany / (until - self.since)))

				
#data set for DA/DB sets
class dataclass:
	def __init__(self, name, path):
		self.bigindex = rtree.index.Index()
		self.curves = dict() #keys are mass values
		self.allmass = list() #list of mass values extracted from file names
		self.grafic = rtree.index.Index()
		self.name = name
		self.path = path

DA = dataclass('DA', topdir/'data/DA')
DB = dataclass('DB', topdir/'data/DB')
