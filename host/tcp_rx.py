#!/usr/bin/python

import os, sys
import commands
import socket
from StringIO import StringIO

from matplotlib.pyplot import *
from mpl_toolkits.mplot3d import Axes3D

from scipy import *
from scipy.ndimage import *
from scipy.linalg import *
from numpy.fft import *
from scipy.signal import convolve2d
from scipy.interpolate import spline

import Image

# Global constants
HOST = '192.168.151.1'
PORT = 1991

BUFFER_SIZE = 1024

# Time information
TSTEP = 20e-3
G = 9.8

# Sharp image dimensions for focus=50
# Width = 7cm
# Height = 5.5cm

WORLD_WIDTH = 5.4e-2
WORLD_HEIGHT = 3.0*WORLD_WIDTH/4.0

IM_WIDTH = 640
IM_HEIGHT = 480

INTERPOLATE_SCALE = 10

# Output files and directory
OUTPUT_DIR = 'output'
IMAGE_NAME = 'saved_im.bmp'
ACCEL_FILE = 'saved_ac.dat'
TOKEN_FILE = 'tokens.dat'

# Delimiting tokens
STRT = '\x00S\x00T\x00R\x00T\x00\n'
STIM = '\x00S\x00T\x00I\x00M\x00\n'
EDIM = '\x00E\x00D\x00I\x00M\x00\n'
STAC = '\x00S\x00T\x00A\x00C\x00\n'
EDAC = '\x00E\x00D\x00A\x00C\x00\n'
ENDT = '\x00E\x00N\x00D\x00T\x00\n'

def save_data(dstring):
    """ Function to extract and save the image and acceleration data
    from the incoming tcp data"""
    global STIM, EDIM, STAC, EDAC
    global OUTPUT_DIR, IMAGE_NAME, ACCEL_FILE

    # Check if we need to create the output directory
    try:
        os.mkdir(OUTPUT_DIR)
    except OSError:
        pass

    # Get the index of the image delimitors
    stim_index = dstring.index(STIM)
    edim_index = dstring.index(EDIM)

    # Get the index of the acceleration data delimitors
    stac_index = dstring.index(STAC)
    edac_index = dstring.index(EDAC)

    acstring = dstring[stac_index+len(STAC)+1:edac_index-1]
    acstring = acstring.replace('\x00', '')

    acvals = acstring.split(';;')
    afile = open(os.path.join(OUTPUT_DIR, ACCEL_FILE), 'w')
    for ac in acvals:
        afile.write(ac.replace(';', ' ')+'\n')

    # Save the image and the data
    imstring = dstring[stim_index+len(STIM)+1:edim_index-1]
    im = Image.open(StringIO(imstring[:-2]))
    im.save(os.path.join(OUTPUT_DIR, IMAGE_NAME))
    afile.close()

class DataHandle(object):
    """ Class to get the polished data handle. This includes the 
    image, the acceleration, position and velocity. In future when
    the gyroscope will be incorporated, the handle will have rotation
    data also"""

    def __init__(self, dstring, acname=None, imname=None):
        """ Extract the data and store the image and other values"""
        global STIM, EDIM, STAC, EDAC

        if acname == None:
            # Get the index of the image delimiters
            stim_index = dstring.index(STIM)
            edim_index = dstring.index(EDIM)

            # Get the index of the acceleration data delimiters
            stac_index = dstring.index(STAC)
            edac_index = dstring.index(EDAC)

            acstring = dstring[stac_index+len(STAC)+1:edac_index-1]
            acstring = acstring.replace('\x00', '')
            self.xaccel, self.yaccel, self.zaccel = [], [], []

            acvals = acstring.split(';;')
            for ac in acvals:
                try:
                    ax, ay, az = [float(i) for i in ac.split(';')]
                    self.xaccel.append(ax)
                    self.yaccel.append(ay)
                    self.zaccel.append(az)
                except ValueError:
                    print 'Invalid acceleration value. Skipping'
        else:
            acdat = loadtxt(acname)
            self.xaccel, self.yaccel, self.zaccel = [acdat[:, 0],
                                                     acdat[:, 1],
                                                     acdat[:, 2]]

        self.ndata = len(self.xaccel)

        if imname == None:
            # Get the image.
            imstring = dstring[stim_index+len(STIM)+1:edim_index-1]
            self.im = Image.open(StringIO(imstring[:-2]))
        else:
            self.im = Image.open(imname)


    def calculate_position(self, linear_drift = True):
        """ Calculate the position from the given acceleration data.
        Note the following assumptions:
        1. The average acceleration has to be zero.
        2. The drift is assumed to be linear. Hence, we do a least
           square fitting of the position and subtract.
        """

        global G, TSTEP
        # Subtract the mean.
        xaccel = array(self.xaccel) - mean(array(self.xaccel))
        yaccel = array(self.yaccel) - mean(array(self.yaccel))
        zaccel = array(self.zaccel) - mean(array(self.zaccel))

        # Integrate twice to get the position.
        xpos = cumsum(cumsum(xaccel))*G*TSTEP*TSTEP
        ypos = cumsum(cumsum(yaccel))*G*TSTEP*TSTEP
        zpos = cumsum(cumsum(zaccel))*G*TSTEP*TSTEP

        # Find the slope of the line 'drift = m*time'
        norm_time = arange(0, TSTEP*self.ndata,
         TSTEP)[:self.ndata].reshape((self.ndata,1))
        self.mx, res, rank, sing = lstsq(norm_time, xpos.T)
        self.my, res, rank, sing = lstsq(norm_time, ypos.T)
        self.mz, res, rank, sing = lstsq(norm_time, zpos.T)

        if linear_drift:
            # Subtract the drift
            self.ypos = ypos - self.my*norm_time.reshape((self.ndata))
            self.xpos = xpos - self.mx*norm_time.reshape((self.ndata))
            self.zpos = zpos - self.mz*norm_time.reshape((self.ndata))
        else:
            self.ypos = ypos
            self.xpos = xpos
            self.zpos = zpos

    def plot_position(self):
        """ Plot the positions in X, Y, Z direction. Note that the
        method calculate_position has to be called first"""

        global TSTEP
        global IM_HEIGHT, IM_WIDTH
        global WORLD_HEIGHT, WORLD_WIDTH
        fig = figure()
        time = arange(0, TSTEP*self.ndata, TSTEP)[:self.ndata]

        print self.xpos.shape, time.shape

        scale_x = IM_HEIGHT/WORLD_HEIGHT
        scale_y = IM_WIDTH/WORLD_WIDTH

        subplot(3,1,1)
        plot(time, self.xpos*scale_x)
        #plot(time, time*self.mx*scale_x, 'r')
        #plot(time, (self.xpos+time*self.mx)*scale_x, 'y.')
        title('X position')

        subplot(3,1,2)
        plot(time, self.ypos*scale_y)
        #plot(time, time*self.my*scale_y, 'r')
        #plot(time, (self.ypos+time*self.my)*scale_y, 'y.')
        title('Y position')

        subplot(3,1,3)
        plot(time, self.zpos)
        #plot(time, time*self.mz, 'r')
        #plot(time, self.zpos+time*self.mz, 'y.')
        title('Z position')

        show()

    def deblurr_kernel(self):
        """ Construct the deblurr kernel from the position information
        """

        global IM_HEIGHT, IM_WIDTH
        global WORLD_HEIGHT, WORLD_WIDTH

        scale_x = IM_HEIGHT/WORLD_HEIGHT
        scale_y = IM_WIDTH/WORLD_WIDTH

        # Find the shift in terms of pixels.
        xpos_pixel = (self.xpos*scale_x).astype(int)
        ypos_pixel = (self.ypos*scale_y).astype(int)

        # Smoothen the position to 10 times the points.
        xlen = len(xpos_pixel)
        ylen = len(ypos_pixel)
        
        xpos_pixel = spline(range(xlen), xpos_pixel,
                            linspace(0, xlen, xlen*INTERPOLATE_SCALE))
        ypos_pixel = spline(range(ylen), ypos_pixel,
                            linspace(0, ylen, ylen*INTERPOLATE_SCALE))
        
        xdim, ydim = abs(xpos_pixel).max(), abs(ypos_pixel).max()
        blurr_kernel = zeros(((xdim+1)*2, (ydim+1)*2))

        for i in range(len(xpos_pixel)):
            blurr_kernel[xdim+xpos_pixel[i], ydim+ypos_pixel[i]]+=1

        return blurr_kernel

def deblur(im, kernel, nsr=0.01):
    """ Weiner deconvolution for deblurring"""
    # Attempt a dumb deconvolution
    if len(im.shape) == 2:
        kx, ky = kernel.shape
        xdim, ydim = im.shape
        nchan = 1
    else:
        kx, ky = kernel.shape
        xdim, ydim, nchan = im.shape
    if nchan == 3:  
        imr = im[:,:,0]
        img = im[:,:,1]
        imb = im[:,:,2]

        imdim = (xdim, ydim)
        IMR = fft2(imr, s=imdim)
        IMG = fft2(img, s=imdim)
        IMB = fft2(imb, s=imdim)

        H = fft2(kernel/sum(kernel), s=imdim)

        IMOUTR = IMR*conj(H)/(H*conj(H) + nsr)
        IMOUTG = IMG*conj(H)/(H*conj(H) + nsr)
        IMOUTB = IMB*conj(H)/(H*conj(H) + nsr)

        imoutr = ifft2(IMOUTR)
        imoutg = ifft2(IMOUTG)
        imoutb = ifft2(IMOUTB)

        imout = zeros((xdim, ydim, 3))
        imout[:,:,0] = imoutr
        imout[:,:,1] = imoutg
        imout[:,:,2] = imoutb

    elif nchan == 1:
        IM = fft2(im, s=(xdim, ydim))
        H = fft2(kernel/sum(kernel), s=(xdim, ydim))
        IMOUT = IM*conj(H)/(H*conj(H) + nsr)
        imout = ifft2(IMOUT)

    return (imout*255.0/imout.max()).astype(uint8)


def tcp_listen():
    """ Listen to the TCP socket and get data"""
    # Wait till you get a socket client

    global HOST, PORT
    global STRT, STIM, EDIM, STAC, EDAC, ENDT
    global TOKEN_FILE

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print 'Waiting for a client'
    sock.bind((HOST, PORT))
    sock.listen(1)
    conn, addr = sock.accept()
    print 'Accepted client ', addr

    dstring = ''
    tokenfile = open(os.path.join(OUTPUT_DIR, TOKEN_FILE), 'w')
    # Start getting data
    while 1:
        data = conn.recv(BUFFER_SIZE)
        dstring += data
        tokenfile.write(data)

        # Check if we need to start reception
        if STRT in data:
            print 'Started reception'
        if STIM in data:
            print 'Starting image reception'
        if STAC in data:
            print 'Starting acceleration data reception'
        if EDAC in data:
            print 'Acceleration reception done'
        if EDIM in data:
            print 'Image reception done'
        if ENDT in dstring:
            print 'Reception complete. Closing connection'
            conn.close()
            return dstring

if __name__  == '__main__':
    # Start listening to TCP socket
    #dstring = tcp_listen();save_data(dstring);dhandle = DataHandle(dstring)
    dhandle = DataHandle(None, os.path.join(OUTPUT_DIR, ACCEL_FILE),os.path.join(OUTPUT_DIR, IMAGE_NAME))
    dhandle.calculate_position(linear_drift = False)
    #dhandle.plot_position()
    #dhandle.im.show()
    blur_kernel = dhandle.deblurr_kernel()
    Image.fromarray(blur_kernel*255.0/blur_kernel.max()).convert('L').save(
        os.path.join(OUTPUT_DIR, 'blur_kernel.bmp'))
    
    robust_kernel = imread('output/robust_kernel.bmp',
     flatten=True)
    im = array(dhandle.im)

    out = deblur(im, blur_kernel)
    #Image.fromarray(out).show()
    Image.fromarray(out.astype(uint8)).convert('RGB').save(
        os.path.join(OUTPUT_DIR, 'deblurred_image.bmp'))

    imblurred = convolve2d(imread('output/saved_im_noshake.bmp', flatten=True),
     blur_kernel/sum(blur_kernel))
    Image.fromarray(imblurred).convert('L').save('output/synthetic.bmp')

    cnt = 0
    try:
        #os.mkdir('output/tmp')
        os.mkdir('tmp')
    except OSError:
        pass
    for scale in linspace(7e-2, 20e-2, 50):
        WORLD_WIDTH = scale
        WORLD_HEIGHT = scale*0.75
        blur_kernel = dhandle.deblurr_kernel()
        '''
        Image.fromarray(blur_kernel*255.0/blur_kernel.max()).convert('L').save(
            os.path.join(OUTPUT_DIR, 'blur_kernel.bmp'))    
        print commands.getoutput('cd output && wine robust_deconv.exe '
                                 'saved_im.bmp blur_kernel.bmp tmp/im_%d.bmp'
                                 ' 0 0.05 1'%cnt)
        '''
        imout = deblur(im[:,:,0], blur_kernel, nsr=0.01)
        Image.fromarray(imout).save('tmp/im_%d.bmp'%cnt)
        cnt += 1
