#!/usr/bin/env python
#******************************************************************************
#  Name:     gamma_filter.py
#  Purpose: ;    gamma MAP adaptive filtering for polarized SAR intensity images
#            Ref: Oliver and Quegan (2004) Understanding SAR Images, Scitech 
#  Usage:             
#    python gamma_filter.py [-h] [-d dims] infile enl
#
#  Copyright (c) 2015, Mort Canty
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

import auxil.auxil as auxil
import auxil.congrid as congrid
import os, sys, time, getopt
import numpy as np
from osgeo import gdal
from osgeo.gdalconst import GDT_Float32, GA_ReadOnly

templates = np.zeros((8,7,7),dtype=int)
for j in range(7):
    templates[0,j,0:3] = 1
templates[1,1,0]  = 1
templates[1,2,:2] = 1
templates[1,3,:3] = 1
templates[1,4,:4] = 1
templates[1,5,:5] = 1
templates[1,6,:6] = 1
templates[2] = np.rot90(templates[0])
templates[3] = np.rot90(templates[1])
templates[4] = np.rot90(templates[2])
templates[5] = np.rot90(templates[3])
templates[6] = np.rot90(templates[4])
templates[7] = np.rot90(templates[5])

tmp = np.zeros((8,21),dtype=int)
for i in range(8):
    tmp[i,:] = np.where(templates[i].ravel())[0] 
templates = tmp

edges = np.zeros((4,3,3),dtype=int)
edges[0] = [[-1,0,1],[-1,0,1],[-1,0,1]]
edges[1] = [[0,1,1],[-1,0,1],[-1,-1,0]]
edges[2] = [[1,1,1],[0,0,0],[-1,-1,-1]]
edges[3] = [[1,1,0],[1,0,-1],[0,-1,-1]]   
    
   
def get_windex(j,cols):
    windex = np.zeros(49,dtype=int)
    six = np.array([0,1,2,3,4,5,6])
    windex[0:7]   = (j-3)*cols + six
    windex[7:14]  = (j-2)*cols + six
    windex[14:21] = (j-1)*cols + six
    windex[21:28] = (j)*cols   + six 
    windex[28:35] = (j+1)*cols + six 
    windex[35:42] = (j+2)*cols + six
    windex[42:49] = (j+3)*cols + six
    return windex

def gamma_filter(k,inimage,outimage,rows,cols,m):
    result = np.copy(inimage[k])
    arr = outimage[k].ravel()
    print 'filtering band %i'%(k+1)
    print 'row: ',
    sys.stdout.flush()    
    for j in range(3,rows-3):
        if j%50 == 0:
            print '%i '%j, 
            sys.stdout.flush()
        windex = get_windex(j,cols)
        for i in range(3,cols-3):
#          central pixel, always from original input image
            g = inimage[k,j,i]            
            wind = np.reshape(arr[windex],(7,7))
#          3x3 compression
            w = congrid.congrid(wind,(3,3),method='linear',centre=True)
#          get appropriate edge mask
            es = [np.sum(edges[p]*w) for p in range(4)]
            idx = np.argmax(es)  
            if idx == 0:
                if np.abs(w[1,1]-w[1,0]) < np.abs(w[1,1]-w[1,2]):
                    edge = templates[0]
                else:
                    edge = templates[4]
            elif idx == 1:
                if np.abs(w[1,1]-w[2,0]) < np.abs(w[1,1]-w[0,2]):
                    edge = templates[1]
                else:
                    edge = templates[5]                
            elif idx == 2:
                if np.abs(w[1,1]-w[0,1]) < np.abs(w[1,1]-w[2,1]):
                    edge = templates[6]
                else:
                    edge = templates[2]  
            elif idx == 3:
                if np.abs(w[1,1]-w[0,0]) < np.abs(w[1,1]-w[2,2]):
                    edge = templates[7]
                else:
                    edge = templates[3] 
            wind = wind.ravel()[edge] 
            var = np.var(wind)
            if var > 0: 
                mu = np.mean(wind)  
                alpha = (1 +1.0/m)/(var/mu**2 - 1/m)
                if alpha < 0:
                    alpha = np.abs(alpha)
                a = mu*(alpha-m-1)
                x = (a+np.sqrt(4*g*m*alpha*mu+a**2))/(2*alpha)        
                result[j,i] = x
            windex += 1  
    print ' done'        
    return result          

def main():
    usage = '''
    Usage:
    ------------------------------------------------
    python %s [-h] [-d dims] filename enl
    
    Run a gamma Map filter in the diagonal elements of a C or T matrix
    ------------------------------------------------''' %sys.argv[0]
    options,args = getopt.getopt(sys.argv[1:],'hd:')
    dims = None
    for option, value in options: 
        if option == '-h':
            print usage
            return 
        elif option == '-d':
            dims = eval(value)  
    if len(args) != 2:
        print 'Incorrect number of arguments'
        print usage
        sys.exit(1)        
    infile = args[0]
    m = int(args[1])    
    gdal.AllRegister()                  
    inDataset = gdal.Open(infile,GA_ReadOnly)     
    cols = inDataset.RasterXSize
    rows = inDataset.RasterYSize    
    bands = inDataset.RasterCount
    if dims == None:
        dims = [0,0,cols,rows]
    x0,y0,cols,rows = dims      
    path = os.path.abspath(infile)    
    dirn = os.path.dirname(path)
    basename = os.path.basename(infile)
    root, ext = os.path.splitext(basename)
    outfile = dirn + '/' + root + '_gamma' + ext    
#  process diagonal bands only
    driver = inDataset.GetDriver() 
    if bands == 9:   
        outDataset = driver.Create(outfile,cols,rows,3,GDT_Float32)
        inimage = np.zeros((3,rows,cols))
        band = inDataset.GetRasterBand(1)
        inimage[0] = band.ReadAsArray(x0,y0,cols,rows)     
        band = inDataset.GetRasterBand(6)
        inimage[1] = band.ReadAsArray(x0,y0,cols,rows)
        band = inDataset.GetRasterBand(9)
        inimage[2] = band.ReadAsArray(x0,y0,cols,rows)        
    elif bands == 4:
        outDataset = driver.Create(outfile,cols,rows,2,GDT_Float32)        
        inimage = np.zeros((2,rows,cols))
        band = inDataset.GetRasterBand(1)
        inimage[0] = band.ReadAsArray(x0,y0,cols,rows)     
        band = inDataset.GetRasterBand(4)
        inimage[1] = band.ReadAsArray(x0,y0,cols,rows) 
    else:
        outDataset = driver.Create(outfile,cols,rows,1,GDT_Float32)
        inimage = inDataset.GetRasterBand(1)  
    outimage = np.copy(inimage)
    print '========================='
    print '    GAMMA MAP FILTER'
    print '========================='
    print time.asctime()
    print 'infile:  %s'%infile
    print 'equivalent number of looks: %i'%m      
    start = time.time() 
    if bands == 9:
        for k in range(3):
            outimage[k] = gamma_filter(k,inimage,outimage,rows,cols,m)
    elif bands == 4:
        for k in range(2):
            outimage[k] = gamma_filter(k,inimage,outimage,rows,cols,m)   
    else:
        outimage = gamma_filter(0,inimage,outimage,rows,cols,m)                  
    geotransform = inDataset.GetGeoTransform()
    if geotransform is not None:
        gt = list(geotransform)
        gt[0] = gt[0] + x0*gt[1]
        gt[3] = gt[3] + y0*gt[5]
        outDataset.SetGeoTransform(tuple(gt))
    projection = inDataset.GetProjection()        
    if projection is not None:
        outDataset.SetProjection(projection) 
    if bands == 9:
        for k in range(3):    
            outBand = outDataset.GetRasterBand(k+1)
            outBand.WriteArray(outimage[k],0,0) 
            outBand.FlushCache() 
    elif bands == 4:
        for k in range(2):    
            outBand = outDataset.GetRasterBand(k+1)
            outBand.WriteArray(outimage[k],0,0) 
            outBand.FlushCache() 
    else:
        outBand = outDataset.GetRasterBand(1)
        outBand.WriteArray(outimage,0,0) 
        outBand.FlushCache()                     
    outDataset = None
    print 'result written to: '+outfile 
    print 'elapsed time: '+str(time.time()-start)                 
              
if __name__ == '__main__':
    main()
    