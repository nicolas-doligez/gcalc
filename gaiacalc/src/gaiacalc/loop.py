import math

from util import *
from show import *

def readsample():
	"""iterator for reading sample from CSV file"""

	samples = list()
	header = None

	#convert columns names to int when they only contain digits
	#except for c3 if --no-prob option
	c1 = int(args.bprp) if args.bprp.isdigit() else None
	c2 = int(args.gabs) if args.gabs.isdigit() else None
	c3 = int(args.prob) if not args.no_prob and args.prob.isdigit() else None

	if args.header:
		#strip newline characters
		#file is opened by argparse.Filetype which has no universal lines argument
		#note also that the encoding utf-8-sig is BOM-aware
		#so CSV files produced by microsoft tools will not trigger errors because of BOM
		header = args.inputfile.readline().rstrip('\r\n')
		columns = header.split(args.separator)

		try :
			#extract column numbers from column names
			#except for c3 if --no-prob option
			c1 or (c1 := columns.index(args.bprp))
			c2 or (c2 := columns.index(args.gabs))
			args.no_prob or c3 or (c3 := columns.index(args.prob))

		except ValueError:
			#if specified column name is not in header
			#start from last to override wholine by first missing name
			c3 or (wholine := f'{args.prob} : no such column')
			c2 or (wholine := f'{args.gabs} : no such column')
			c1 or (wholine := f'{args.bprp} : no such column')

			if args.exec:
				log(wholine + '\n')
				exit()
			else:
				#wholine will be displayed on web page
				raise ColumnsException(wholine)

		#return header (only if the file has header)
		yield header

	for line in args.inputfile:
		line = line.replace(args.decimal,'.').rstrip('\r\n')
		columns = line.split(args.separator)
		bprp = float(columns[c1]) if columns[c1] else None
		gabs = float(columns[c2]) if columns[c2] else None
		prob = float(columns[c3]) if not args.no_prob and columns[c3] else None

		#we filter any line missing bprp or gabs
		if bprp and gabs \
		   and (not args.max_bprp or bprp < args.max_bprp) \
		   and (not args.min_bprp or bprp < args.min_bprp) \
		   and (not args.max_gabs or gabs > args.max_gabs) \
		   and (not args.min_gabs or gabs < args.min_gabs):

			#keep the sample
			yield [line, bprp, gabs, prob]

	                
def addmass(s, data):
	"""append mass and temp values to input sample list"""

	m = t = 0.0
	if s[1] and s[2]:
		#only when bprp and gabs are known
	
		#float coords scaled to 0..1000 range
		x = (s[1] - data.rect.xmin) / data.dx
		y = (s[2] - data.rect.ymin) / data.dy
		
		#integer coords
		i = math.floor(x)
		j = math.floor(y)
		
		if i >= args.grid-1 or j >= args.grid-1:
			#this is a sample outside grid index
			m,t = 0.0,0.0
			
		else:
			#extract mass from 4 surrounding points
			m11 = data.grid[args.grid*i + j]
			m12 = data.grid[args.grid*i + j+1]
			m21 = data.grid[args.grid*(i+1) + j]
			m22 = data.grid[args.grid*(i+1) + j+1]
			
			#compute bilinear interpolation
			mbi = m11[0]*(1-x+i)*(1-y+j) \
				+ m12[0]*(1-x+i)*(y-j) \
				+ m21[0]*(x-i)*(1-y+j) \
				+ m22[0]*(x-i)*(y-j)
			tbi = m11[1]*(1-x+i)*(1-y+j) \
				+ m12[1]*(1-x+i)*(y-j) \
				+ m21[1]*(x-i)*(1-y+j) \
				+ m22[1]*(x-i)*(y-j)
			
			#keep it only if all surrounding points have a mass value
			m = mbi if m11[0] and m12[0] and m21[0] and m22[0] else 0.0
			t = tbi if m11[1] and m12[1] and m21[1] and m22[1] else 0.0

	s.append(m)
	s.append(t)
	return s
	
	
def writesample(f,s):
	if args.format == 'bin':
		f.write(struct.pack('!f',s[-2])) #mass
		f.write(struct.pack('!f',s[-1])) #Teff
	else:
		#use localized values (dots or commas)
		if not args.no_prob:
			mass = str(s[-2])
			Teff = str(s[-1])
			f.write(f'{s[0]};{mass};{Teff}\n'.replace(';',args.separator).replace('.',args.decimal))
		else:
			mass = str((s[-4]+s[-2])/2 if s[-4] and s[-2] else s[-4] or s[-2])
			Teff = str((s[-3]+s[-1])/2 if s[-3] and s[-1] else s[-3] or s[-1])
			masserr = str(abs(s[-4]-s[-2])/2/s[-4] if s[-4] and s[-2] else 0.0)
			Tefferr = str(abs(s[-3]-s[-1])/2/s[-3] if s[-3] and s[-1] else 0.0)
			f.write(f'{s[0]};{mass};{Teff};{masserr};{Tefferr}\n'.replace(';', args.separator).replace('.',args.decimal))

	
def mainloop():
	"""run once for sampling, either for shell launching or webserver"""

	with performance('computing samples') as perf:

		if not args.inputfile:
			log('input from standard input\n')
		
		#extension for header
		mode = 'wb' if args.format == 'bin' else 'w'
		newcol = ";mass;Teff" if not args.no_prob else ";mass;Teff;masserr;Tefferr"
		newcol = newcol.replace(';', args.separator)
		
		#use output option or defaults to stdout
		f = args.output and open(args.output, mode) or sys.stdout

		#this is the generator to call for each line
		getsample = readsample()
		
		#write header output if any header
		if args.header:
			header = next(getsample) #extract first line
			mode == 'w' and f.write(f'{header}{newcol}\n') #not for binary output
			
		#then read and process each line of input file
		howmany = 0
		result = list()
		for sample in getsample:
			howmany += 1
			if not args.no_prob:
				sample = addmass(sample, DA if sample[3] > 0.5 else DB)
			else:
				#we add both DA and DB
				#then writesample will compute mean and error rate
				sample = addmass(addmass(sample, DA), DB)

			try:
				writesample(f, sample)
			except BrokenPipeError:
				log('exiting with Broken Pipe\n')
				break;
				
			if howmany < 20002:
				#collect results up to 20000 points
				#these are used to draw matplotlib views for option --show or in webserver
				#we limit the number of samples to display under 20000
				#to avoid waiting too long for an anyway unusable result
				#so any sample above 20000 is not recorded here
				#note that you have an error message displayed in webserver page
				result.append(sample)
			
		perf.howmany = howmany
		return result
