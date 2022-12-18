import threading
import cherrypy
from cherrypy.lib import static

from util import *
from loop import *

class webserver():
	wholine = ''
	samples = None
	indexpage = ''
	indexcss = ''
	
	@cherrypy.expose
	def index(self):
		
		#backup wholine and erase it
		wholine = self.wholine
		self.wholine = ''

		if not self.indexpage or not self.indexcss:
			with open(topdir/"data/page.html") as f:
				self.indexpage = f.read()
		
		return self.indexpage % wholine

	
	@cherrypy.expose
	def page(self, name):
		return static.serve_file(str(topdir/'data'/name))
	

	@cherrypy.expose
	def upload(self, **kw):

		thefile = kw.get('myfile').file
		if not thefile:
			log('no input file name, using samples.csv\n')
		else:			
			with open(args.data/'input.csv','wb') as f:
				while True:
					data = thefile.read(8192)
					if not data:
						break
					f.write(data)
		
		args.separator = kw.get('separator')
		args.separator = '\t' if args.separator == '\\t' else args.separator
		args.decimal = kw.get('decimal')
		args.header = kw.get('header')
		args.bprp = kw['bprp']
		args.gabs = kw['gabs']
		args.prob = kw.get('prob')
		args.no_prob = kw.get('no-prob')
		args.inputfile = open(args.data/'input.csv') if thefile else open(topdir/'data/samples.csv')
		args.output = (args.data/'output.csv').absolute()

		if not args.header:
			if not (args.bprp.isdigit() and args.gabs.isdigit() and (not args.prob or args.prob.isdigit())):
				self.wholine = 'columns should be number when no header in file'
				raise cherrypy.HTTPRedirect('index')

		try:
			self.samples = mainloop()
		except ColumnsException as e:
			log('webserver error %s\n' % str(e))
			self.wholine = str(e)
			raise cherrypy.HTTPRedirect('index')
		except Exception as e:
			log('webserver error %s\n' % str(e))
			self.wholine = 'some strange error occured, ask doligez.julie@gmail.com'
			raise cherrypy.HTTPRedirect('index')
		finally:
			args.inputfile.close()
		
		#path = os.path.join(os.getcwd(), os.path.dirname(__file__), 'output.csv')
		return static.serve_file(args.output, 'application/x-download', 'attachment', 'output.csv')


	@cherrypy.expose
	def drop(self, file, **kw):
		return static.serve_file(topdir/'data'/file, 'application/x-download', 'attachment', file)
		

	@cherrypy.expose
	def showdata(self):
		if not self.samples:
			self.wholine = 'you have to send data first'
			raise cherrypy.HTTPRedirect('index')
			
		if len(self.samples) > 20000:
			self.wholine = 'too much data (> 20000)'
			raise cherrypy.HTTPRedirect('index')

		showwindows(self.samples)

		#see https://www.freecodecamp.org/news/how-to-embed-interactive-python-visualizations-on-your-website-with-python-and-matplotlib/
		with open(topdir/'data/figure.html','w') as htmlfile:
			htmlfile.write(mpld3.fig_to_html(DA.figure))
		return static.serve_file(str(topdir/'data/figure.html'))


	@cherrypy.expose
	def autokill(self, **kw):
		#exit python process
		#argument allowed to bypass browser caching with random arg (see javascript code)
		#use a single line delayed exit for the daemon process
		#and meanwhile return a bye html page
		#linux is expected to run daemon therefore no exit needed
		if sys.platform != 'linux':
			threading.Thread(target=lambda: time.sleep(1) or os._exit(1)).start()
		return static.serve_file(str(topdir/'data/bye.html'))
