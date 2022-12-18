
import sys
import math
import itertools
import rtree
import multiprocessing as mp

from util import *

class rectclass:
	xmin,xmax,ymin,ymax = (0,0,0,0)
	def __str__(self):
		return f'{self.xmin}\n{self.xmax}\n{self.ymin}\n{self.ymax}\n'


def readcurve(datpath):
	""" read reference curve and find wrong parts to remove"""

	with open(datpath) as data:
		lines = data.readlines()
		
	#skip the first line with column names
	drop = lines.pop(0)

	points = list()
	for line in lines:
		val = line.split()
		#x coordinate is computed as BP3 - RP3
		#z coordinate is the temperture Teff
		x,y,z = float(val[6]) - float(val[7]), float(val[5]), float(val[0])
		points.append((x,y,z))
		
	#input files are not always sorted
	points = sorted(points, key=lambda x: x[1])
	
	#we have to take care of duplicates
	#otherwise we end up with zero distance then divide by zero errors
	#(we have a duplicate in 129DA.dat for gabs = 17.026278170132585)
	#the following will remove duplicates
	#see https://stackoverflow.com/a/7961390
	points = list(dict.fromkeys(points))
	
	#remove curves part going backward (seen in DA only)
	maxX = max([p[0] for p in points]) #find rightmost point
	cut1 = [p[0] for p in points].index(maxX) #find index of rightmost point
	
	#detect and remove end of curves going up (only for DA)
	segments = zip(points[:cut1-1], points[1:cut1])
	slopes = [(p2[1] - p1[1]) / (p2[0] - p1[0]) for p1,p2 in segments]
	angles = zip(slopes[:-1], slopes[1:]) #couples of slopes around each point
	rates = [s2/s1 for s1,s2 in angles]
	
	#then detect where slope rises over 20%
	flex = [1 if s2/s1 > 1.2 else 0 for s1,s2 in zip(slopes[:-1], slopes[1:])]
	tail = 100 #check this number of points from end of curve
	limit = (flex[-tail:]+[1]).index(1) #look for first "one" value, last value is "one"
	cut2 = cut1 -tail - 1 + limit #index of last point to retain
	
	return points, cut1, cut2


def indexcurves(data):
	"""build geom index for curves"""

	bigid = 0 #id for bigindex
	with open(args.data / ('bigindex%s.trace'%data.name),'w') as trace: #debug file for bigindex

		#read all .dat files in current directory
		for datpath in sorted(data.path.rglob('*.dat')):

			filename = datpath.parts[-1] 
			mass = float(filename[0] + '.' + filename[1:-6])
			data.allmass.append(mass)
			points,cut1,cut2 = readcurve(datpath)

			#cut the points list according to readcurve algorithm
			points = points[:cut2]

			#geom index for this curve
			curveindex = rtree.index.Index()
			rank = 0

			for x,y,z in points:
				
				#insert in curve index and in general index
				#in curve index the value is the rank of the point
				#in general index the value is the mass for this curve
				curveindex.insert(rank, (x,y)*2, rank)
				data.bigindex.insert(bigid, (x,y)*2, mass)
				
				#debug file
				args.debug and trace.write("bigid %d x %f y %f mass %f\n" % (bigid,x,y,mass))
				
				rank += 1
				bigid += 1
				
			data.curves[mass] = (points, curveindex)

	#do not forget to sort mass values
	#because we use the order to find the curve just above or below the nearest curve
	data.allmass.sort()


def getdist(xS, yS, curve):
	"""compute distance from sample to curve"""

	#see http://www.sunshine2k.de/coding/java/PointOnLine/PointOnLine.html
	#using this web page, things may be better coded than below
	#we keep that in the to-do list :)
	
	#get the points list for this curve
	#and the geom index for this curve
	points, index = curve

	#use the geom index to find the nearest point on this curve
	found = next(index.nearest([xS, yS]*2))

	#do not allow first point as nearest
	#otherwise the "before" point will be the last of the curve
	#because negative index in a list will count from end of list
	if found == 0 or found == len(index) -1:
		raise EndOfCurveException('nearest point is end of curve')
	
	#look for the best point, and two points around it (before and after on curve)
	before,nearest,after = points[found-1], points[found], points[found+1]
	xN,yN,zN = nearest
	xA,yA,zA = before
	xB,yB,zB = after
	
	#we have the best/nearest point given by the geom index
	#from this point, we have 2 segment toward "before" or "after"
	#then we have 3 different cases
	#we need to consider 2 angles between the segment (sample,nearest)
	#and the segment (nearest, before) or the segment (nearest, after)

	#first case : one acute angle and one obtuse angle
	#we choose the acute angle and the corresponding segment
	#then the distance to the curve is the distance beetween the choosen segment and the sample point

	#second case : both angles are acute
	#(this may only happen if the angle between the 2 segments is lower than 180 degrees)
	#then we can project the sample point on both segments and compute the distance
	#the correct distance between the sample and the curve is the lowest distance

	#third case : both angles are obtuse
	#(this may only happen if the angle between the 2 segments is bigger than 180 degrees)
	#then we cannot project the point on any segment
	#the correct distance is the distance to the nearest point

	#to check angles, we compute their cosinus
	#the formula is for segments defined by dx1,dy1 and dx2,dy2 :
	#cosinus = (dx1*dx2 + dy1*dy2) / norm1 / norm2

	#segment between sample and nearest
	dxS = xS - xN
	dyS = yS - yN
	normS = math.sqrt(dxS**2 + dyS**2)

	#segment between nearest and "before"
	dxB = xB - xN
	dyB = yB - yN
	normB = math.sqrt(dxB**2 + dyB**2)

	#segment between nearest and "after"
	dxA = xA - xN
	dyA = yA - yN
	normA = math.sqrt(dxA**2 + dyA**2)
	
	#angle towards "before" S^N^B
	cosB = (dxS*dxB + dyS*dyB) / normS / normB
	
	#angle towards "after" S^N^A
	cosA = (dxS*dxA + dyS*dyA) / normS / normA

	#distances NS, NA, NB
	lenNS = math.sqrt(dxS**2 + dyS**2)
	lenNA = math.sqrt(dxA**2 +dyA**2)
	lenNB = math.sqrt(dxB**2 +dyB**2)

	if cosA*cosB < 0:
		#first case, we keep the obtuse angle with cosinus > 0
		xx,yy,zz,cos,lenNP = (xB,yB,zB,cosB,lenNB) if cosB>0 else (xA,yA,zA,cosA,lenNA)
		above,dist = segdist(xS,yS,xN,yN,xx,yy)

		#interpolate temp between N and P (P is either B or A)
		temp = zN + (zz-zN) * lenNS*cos / lenNP
		return above,dist,temp
	
	if cosA>=0 and cosB>=0:
		#second case, compute both distances
		above1,d1 = segdist(xS,yS,xN,yN,xB,yB)
		above2,d2 = segdist(xS,yS,xN,yN,xA,yA)

		if above1 ^ above2:
			#then we have a problem, the flags should be the same ??
			log("above flag error x %f y %f\n" % (xS,yS))
			raise AboveFlagException('above flag error')

		#keep the shortest distance to segment NA or NB
		#and retain the cosinus for angle N^S^B or N^S^A
		#and retain the length of the segment NB or NA
		#and retain the temp of B or A
		dist,cos,lenNP,zz = (d1,cosB,lenNB,zB) if d1<d2 else (d2,cosA,lenNA,zA)

		#interpolate temp between N and P (P is either B or A)
		temp = zN + (zz-zN) * lenNS*cos / lenNP
		return above1,dist,temp

	if cosA<=0 and cosB<=0:
		#third case, distance to the nearest point
		#above if sample y is greater than nearest y
		#temperature is nearest point temp
		return dyS>0,normS,zN

	
def segdist(x0,y0,x1,y1,x2,y2):
	"""distance from point P0 to line P1-P2 and position above/below"""
	
	#apply the formula to compute distance from P0 to segment P1,P2
	#note : no need to check for zero distP1P2 since we removed duplicate points in curves
	#see formula here https://en.wikipedia.org/wiki/Distance_from_a_point_to_a_line#Line_defined_by_two_points

	distP1P2 = math.sqrt((x2-x1)**2 + (y2-y1)**2)
	distP0L12 = abs((x2-x1) * (y1-y0) - (x1-x0) * (y2-y1)) / distP1P2

	#now we need to test if P0 is above D12
	#D12 equation is ax + by + c = 0
	#above or below depends on sign of (ax+by+c)
	#but depends also on sign of b
	#because ax+by+c=0 is equivalent to -ax-by-c=0

	#equation of a line passing through two points A(1, 7) and B(2, 3)
	#(x - 1) / (2 - 1)  =   (y - 7) / (3 - 7)
	#see https://onlinemschool.com/math/library/analytic_geometry/line/#h4
	
	a = y1-y2
	b = x2-x1
	c = x1*y2 - x2*y1
	above = b * (a*x0 + b*y0 + c) > 0

	return above,distP0L12


def interpolate(bprp, gabs, DADB):
	"""
	interpolate the mass value from the curves
	using geometrical indexes to find nearest point in curves
	this will return mass zero whenever the sample is above the highest curve
	or below the lowest curve
	"""

	try:
		data = DA if DADB else DB
                
		#get the mass from the nearest point in any curve
		mass1 = next(data.bigindex.nearest([bprp,gabs]*2, objects=True)).object

		#compute distance and position (above or below the curve)
		above1,dist1,temp1 = getdist(bprp, gabs, data.curves[mass1])

		#depending on the position (above or under),
		#consider the next curve rank (above or under) to use for interpolation
		#we use the sorted list of curves mass
		rank = data.allmass.index(mass1) + (1 if above1 else -1)

		if rank < 0:
			#negative list index will count from the end
			#this is forbidden here, we want an exception
			raise BelowFirstCurveException('below first curve')

		if rank >= len(data.allmass):
			raise AboveLastCurveException('above last curve')

		#now find the second curve
		#will also raise error is rank bigger than list size
		mass2 = data.allmass[rank]

		#compute distance and position (above or below the curve)
		above2,dist2,temp2 = getdist(bprp, gabs, data.curves[mass2])

		#if point is above for both curves,
		#then curves are not correctly ordered
		#in other words, they crossed
		#then we will not extrapolate in this case
		if above1 == above2:
			raise CrossingCurvesException('crossing curves')

		#here comes the interpolation computing
		#very basic formula, provided we found correct values before !!
		mass = mass1 + dist1 * (mass2 - mass1) / (dist1 + dist2)
		temp = temp1 + dist1 * (temp2 - temp1) / (dist1 + dist2)
		return mass,temp

	except (BelowFirstCurveException, AboveLastCurveException, EndOfCurveException):
		#we get here if we are above higher curve or below lowest curve
		#we choose no interpolation in this case, and return mass zero
		return 0.0,0.0

	except (AboveFlagException, CrossingCurvesException):
		#this will trap errors caused by misformed curves
		#curves are expected to be increasing
		#and to represent mathematical fonctions (one single value for any given x-coordinate)
		#they should never cross, as the intersection would have 2 mass values
		#if wrong, we return here None values
		return None,None
        

def buildgrid(DADB):
	"""build and store grid index"""

	data = DA if DADB else DB
        
	with performance(f'building {data.name} geom index') as perf:
		indexcurves(data)
		perf.howmany = len(data.bigindex)
		
	with performance(f'building {data.name} grid index', howmany=args.grid**2):
		
		#find coordinates of enclosing rectangle
		xx = [p[0] for c in data.curves for p in data.curves[c][0]]
		yy = [p[1] for c in data.curves for p in data.curves[c][0]]
		data.rect = rectclass()
		data.rect.xmin = min(xx)
		data.rect.xmax = max(xx)
		data.rect.ymin = min(yy)
		data.rect.ymax = max(yy)
		
		#compute grid step
		data.dx = (data.rect.xmax - data.rect.xmin)/args.grid
		data.dy = (data.rect.ymax - data.rect.ymin)/args.grid
		
		#make list of args.grid*args.grid grid points
		#each element has the same data as any sample, needed to match interpolate function interface
		x0,y0,dx,dy = data.rect.xmin, data.rect.ymin, data.dx, data.dy
		gridpoints = [(x0+i*dx,y0+j*dy,DADB) for i in range(args.grid) for j in range(args.grid)]

		#testing for frozen bundle environment
		#see https://pyinstaller.org/en/stable/runtime-information.html
		if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
			
			#we are running a frozen version built by pyinstaller
			#cannot launch multiprocessing
			#not clear if it should work in Windows, see below
			#nevertheless, we compute the grid indexes in the same process
			#this is lengthy, but it will not crash :)
			
			#from https://docs.python.org/3/library/multiprocessing.html
			#Warning The 'spawn' and 'forkserver' start methods cannot currently be used
			#with “frozen” executables (i.e., binaries produced by packages
			#like PyInstaller and cx_Freeze) on Unix. The 'fork' start method does work.

			log('single process grid computing... quite long :(')
			data.grid = itertools.starmap(interpolate, gridpoints)

		else:
			#running from source code or regular package (installed with pip3)
			#we are allowed to use multiprocessing package
			log('launching %s subprocesses...\n' % mp.cpu_count())
			with mp.Pool(mp.cpu_count()) as pool:
				#distribute work among processes with 100 samples chunks
				#100-chunks will reduce communication overhead between processes
				data.grid = pool.starmap(interpolate, gridpoints, 100)

		#we have one index file and one more verbose debug file
		with open(args.data / (data.name + '.grid'), 'w') as f1, \
			 open(args.data / (data.name + '.debug'), 'w') as f2:
			
			#enclosing rectangle
			f1.write(str(data.rect))
			f2.write(str(data.rect))
			
			k = 0
			for mass,temp in data.grid:

				#write only mass/temp values in index
				#mass/temp maybe None in case of interpolation error
				f1.write('%f;%f\n' % (mass if mass else 0.0, temp if temp else 0.0))

				#compute point coords for debug file
				x = data.rect.xmin + data.dx * k%args.grid
				y = data.rect.ymin + data.dy * k//args.grid
				args.debug and f2.write(f'i {k%args.grid} j {k//args.grid} x {x} y {y} mass {mass} temp {temp}\n')
				k += 1
					
					
def readgrid(data):
	"""read grid index from file"""

	gridfile = data.path.with_name(data.name + '.grid')
	with open(gridfile) as f:
		data.rect = rectclass()
		
		#top 4 values are min/max
		data.rect.xmin = float(f.readline()[:-1])
		data.rect.xmax = float(f.readline()[:-1])
		data.rect.ymin = float(f.readline()[:-1])
		data.rect.ymax = float(f.readline()[:-1])

		#everything else is the grid index table
		data.grid = [tuple(map(float, line.split(';'))) for line in f]


def initgrids():
	"""build grid index or load from disk"""
	
	#look for both index files in the current dir
	#if one or both is missing, we have to create them
	args.force and log('forced reindexing option\n')
	if args.force or \
	   not (args.data/'DA.grid').is_file() or \
	   not (args.data/'DB.grid').is_file():
		log("computing new index files\n")
		buildgrid(DADB=True)  #this is DA
		buildgrid(DADB=False) #this is DB

	#we are now sure that index files exist on disk
	with performance("loading both index from files", howmany=args.grid**2):
		for data in (DA,DB):
			readgrid(data)
			data.dx = (data.rect.xmax - data.rect.xmin)/args.grid
			data.dy = (data.rect.ymax - data.rect.ymin)/args.grid
