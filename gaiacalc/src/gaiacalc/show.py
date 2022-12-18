import numpy as np

from util import *
from index import *

#import section for matplotlib
#we use tk interface to manage windows
#because this also works with macos
#prerequisite : run this as admin in macos : brew install python-tk
#see https://stackoverflow.com/questions/61218237/how-can-i-install-tkinter-for-python-on-mac

import matplotlib
matplotlib.use('TkAgg') #change this before importing pyplot
import matplotlib.pyplot as plot
import mpld3

#define plot sizes for samples and for curves
defplot = plot.rcParams['lines.markersize'] ** 2 #this is default value
bigplot = defplot / 2
smallplot = defplot / 64

lastone = None #last point displayed in hover() callback

def showgrid(data):
	"""draw points for grid index"""

	row = np.linspace(data.rect.xmin, data.rect.xmax, args.grid+1)
	col = np.linspace(data.rect.ymin, data.rect.ymax, args.grid+1)
	X = np.empty((args.grid**2,))
	Y = np.empty((args.grid**2,))
	for k in range(args.grid**2):
		X[k] = row[k//args.grid]
		Y[k] = col[k%args.grid]
	for k in range(args.grid**2):
		if not data.grid[k][0]:
			X[k] = Y[k] = None

	#we filter out values 0.0 and None
	#in both case the grid is not displayed
	#(None is for exception raised in code,
	# and zero is for projection on curve is not possible)
	X = [x for x in X if x]
	Y = [y for y in Y if y]
	plot.scatter(X,Y, s=smallplot, c="0.8")


def showcurves(data):
	"""plot curves and show truncated parts"""

	#plot params
	kwargs1 = {'color': 'k', 'linestyle': '-', 'linewidth': 0.5, 'marker': 'o', 'markersize': 1.5}
	kwargs2 = {'color': 'r', 'linestyle': '-', 'linewidth': 0.5, 'marker': 'o', 'markersize': 3.0}
	kwargs3 = {'color': 'r', 'linestyle': '-', 'linewidth': 0.5, 'marker': 'o', 'markersize': 1.5}

	#we start again from files
	#because removes parts where not stored in curves table when loaded
	
	#read all .dat files in current directory
	for datpath in sorted(data.path.rglob('*.dat')):

		filename = datpath.parts[-1] 
		mass = float(filename[0] + '.' + filename[1:-6])
		points,cut1,cut2 = readcurve(datpath)

		#plot what is kept
		plot.plot(*list(zip(*points))[0:2], **kwargs1)
		#plot up-slope part
		plot.plot(*list(zip(*points[cut2:cut1]))[0:2], **kwargs2)
		#plot backward part
		plot.plot(*list(zip(*points[cut1:]))[0:2], **kwargs3)


def tempcolor(temp):

	#define some color scaling from red (hot) to blue (cold)
	#temp in DA/DB curves extend from 3000 to 80000
	#we use square root to get progressive color (we could use log also :)

	#below 4000  : RGB = (0, 0, 0.5)
	#up to 6000  : RGB = (0, 0, 1)
	#up to 8000  : RGB = (1, 0, 1)
	#up to 10000 : RGB = (1, 0, 0)
	#up to 20000 : RGB = (1, 1, 0)
	#above 20000 : RGB = (1, 1, 0)

	R,G,B = 0,0,0

	#this is not good goding, need to be explained :(
	#we avoid many if structures here,
	#by using and to test then set variables
	#each line begins by True, just to allow aligning the testing part
	#setting variables uses := allocations which are expressions, allowed as "and" arguments
	#and allocations need to be parenthesized in this case
	#quite ugly but it works and reduces number of lines
	
	True and     0 < temp <=  4000 and (B := 127)
	True and  4000 < temp <=  6000 and (B := 127+128*(temp-4000)/2000)
	True and  6000 < temp <=  8000 and (B := 255) and (R := 256*(temp-6000)/2000)
	True and  8000 < temp <= 10000 and (R := 255) and (B := -256*(temp-10000)/2000)
	True and 10000 < temp <= 20000 and (R := 255) and (G := 256*(temp-10000)/10000)
	True and 20000 < temp <= 99999 and (R := 255) and (G := 255)

	#color format is like '#RRGGBB' with hex values RR, GG, BB
	color = '#%02x%02x%02x' % (int(min(255,max(0,R))), \
							   int(min(255, max(0,G))), \
							   int(min(255, max(0, B))))
	return color


def showsamples(samples, data):
	"""plot samples and show those having an interpolated mass"""

	#filter DA or DB samples
	samples = [s for s in samples if ((data==DA and s[3]>0.5) or ((data==DB and s[3]<0.5)))]
	X = [s[1] for s in samples]
	Y = [s[2] for s in samples]

	#black when mass is zero for maria and/or julie
	colors = ["black" if s[4]*float(s[0].split(args.separator)[4])==0 else tempcolor(s[5]) for s in samples]

	#add new geom index used to display sample when mouse hovers on it
	rank = 0
	for s in samples:
		data.grafic.insert(rank, (s[1],s[2])*2, s)
		rank += 1

	#display samples points
	data.scatter = plot.scatter(X, Y, s=bigplot, c=colors, marker='o')

        
def hover(event):
	"""display one line of info when mouse on a sample in active window"""
	#see https://stackoverflow.com/a/47166787

	global lastone #remember last sample to display only once

	#find which window to select correct grafic index
	fig = plot.gcf()
	data = DA if plot.gcf() == DA.figure else DB

	if event.inaxes == plot.gca():
		cont, ind = data.scatter.contains(event)
		if cont:
			#integer coords in range 0..1000
			i = round((event.xdata - data.rect.xmin) / data.dx)
			j = round((event.ydata - data.rect.ymin) / data.dy)

			#find sample from geom index
			sample = next(data.grafic.nearest([event.xdata, event.ydata]*2, objects=True)).object

			if sample != lastone:
				lastone = sample
				#display coords, EDR3 name and mass (maria/julie)
				maria = float(sample[0].split(args.separator)[4])
				julie = sample[4]
				temp = sample[5]
				print(f'coords {event.xdata:.3f} {event.ydata:.3f}   grid {i} {j}   {sample[1]}   mass {maria:.3f} / {julie:.3f}   Teff {temp:.2f}')


def showwindows(samples):
	"""display results"""

	#now we draw everything with matplotlib
	for data in (DA,DB):
		data.figure = plot.figure(figsize=(12,12), label=data.name) #width/height unit = inches
		showgrid(data)
		showcurves(data)
		showsamples(samples, data)
		data.figure.canvas.mpl_connect("motion_notify_event", hover)
		data.figure.gca().invert_yaxis() #upside down as usual for HRD diagram
		"""
		cmap = matplotlib.cm.cool
		norm = matplotlib.colors.Normalize(vmin=5, vmax=10)
		ax = data.figure.gca()
		data.figure.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap),
							 cax=ax, orientation='vertical', label='Teff temperature')		
		"""

