#!/usr/bin/env python

import os, sys
import commands

from matplotlib.pyplot import *
from scipy import *
from scipy.signal import *
from scipy.linalg import *
from scipy.interpolate import spline
from scipy.ndimage import *
from scipy.special import *
from numpy import fft

import Image
from image3d import *

accel_data_file = '../output/cam/saved_ac.dat'
T = 10e-3
G = 9.8

def register(impure, imblur, kernel=None):
    ''' Register and shift the pure image using fourier correlation method.'''
    IMPURE = fft.fft2(impure)
    IMBLUR = fft.fft2(imblur)

    IMSHIFT = IMPURE*conj(IMBLUR)/(abs(IMPURE)*abs(IMBLUR))
    if kernel is not None:
        xdim, ydim = impure.shape
        KERNEL = fft.fft2(kernel, s=(xdim, ydim))
        IMSHIFT *= abs(KERNEL)/KERNEL
    imshift = real(fft.ifft2(IMSHIFT))
    imshift *= 255.0/imshift.max()
    x, y = where(imshift == imshift.max())
    xdim, ydim = imshift.shape
    if x >= xdim//2:
        x = x- xdim
    if y >= ydim//2:
        y = y - ydim
    
    shift_kernel = zeros((2*abs(x)+1, 2*abs(y)+1))
    shift_kernel[abs(x)-x,abs(y)-y] = 1
    shifted_im = fftconvolve(impure, shift_kernel, mode='same')

    return shifted_im

def _try_deblur(kernel, im, nsr, mfilter):
    ''' Another try at deblurring'''
    kernel = kernel.astype(float)/kernel.sum()
    x, y = im.shape
    IM = fft.fft2(im, s=(x,y))
    H  = fft.fft2(kernel, s=(x,y))
    F  = fft.fft2(mfilter, s=(x,y))/IM
    
    IMOUT = conj(H)*IM/(abs(H)**2 + nsr*(abs(F)**2))
    imout = real(fft.ifft2(IMOUT))
    return imout.astype(float)
    
def _deblur(kernel, im, nsr, niters=4):
    ''' Deblur a single channel image'''
    x1, y1= im.shape
    x2, y2 = kernel.shape
    # Pad the image. We are getting unnecessary shift otherwise.
    x = x1+2*x2; y=y1+2*y2
    imtemp = zeros((x, y), dtype='uint8')
    imtemp[x2:-x2, y2:-y2] = im # Main image
    imtemp[:x2, :y2] = im[-x2:,-y2:]  # Left top
    imtemp[-x2:, :y2] = im[:x2, -y2:] # Right top
    imtemp[-x2:, -y2:] = im[:x2, :y2] # Right bottom
    imtemp[:x2, -y2:] = im[-x2:, :y2] # Left bottom
    imtemp[x2:-x2, :y2] = im[:, -y2:] # top
    imtemp[x2:-x2, -y2:] = im[:, :y2] # bottom
    imtemp[:x2, y2:-y2] = im[-x2:, :] # left
    imtemp[-x2:, y2:-y2] = im[:x2, :] # right
    im = imtemp
    #x, y = im.shape
    # Create the ffts
    IM = fft.fft2(im, s=(x,y))
    H  = fft.fft2(kernel, s=(x,y))
    # First time transformation is just wiener.
    IMOUT = conj(H)*IM/(abs(H)**2+nsr)

    # Now we do reguralization.
    for i in range(niters):
        IMDIFF = (IM - H*IMOUT)/IM
        IMOUT = conj(H)*IM/(abs(H)**2+nsr*IMDIFF)
    imout = fft.ifft2(IMOUT)
    return imout.astype(float)[:x1, :y1]

def estimate_g(data, start=0, end=-1):
    '''Estimate gravity vector using projection onto unit sphere
       What we need to do is minimize the error given that every point lies
       on a unit sphere.
    '''
    if end == len(data[:,0]):
        end = -1
    # Assume that the data is a stack of x,y, z acceleration
    mx = mean(data[start:end, 0])
    my = mean(data[start:end, 1])
    mz = mean(data[start:end, 2])
    norm_g = sqrt(mx**2 + my**2 + mz**2)
    output = zeros_like(data)
    output[:,0] = mx/norm_g; output[:,1] = my/norm_g; output[:,2] = mz/norm_g; 

    return output

def construct_kernel(xpos, ypos, d=1.0, interpolate_scale = 1):
    '''Construct the kernel from the position data'''
    ntime = len(xpos)
    xpos = d*spline(range(ntime), xpos,
        linspace(0, ntime, ntime*interpolate_scale))
    ypos = d*spline(range(ntime), ypos,
        linspace(0, ntime, ntime*interpolate_scale))
    ntime *= interpolate_scale
    #xpos -= mean(xpos); ypos -= mean(ypos)
    xmax = max(abs(xpos)); ymax = max(abs(ypos))
    kernel = zeros((2*xmax+1, 2*ymax+1), dtype=uint8)
    for i in range(ntime):
        kernel[int(xmax+xpos[i]), int(ymax+ypos[i])] += 1
    return kernel.astype(float)/(kernel.sum()*1.0)

def estimate_simple_pos(accel, start, end):
    ''' Simple calculation of position using just integration'''
    if end == len(accel[:,0]):
        end = -1
    # Estimate g first
    g_vector = estimate_g(accel)
    accel -= g_vector
    # Convert acceleration into m/s^2
    accel *= G
    xaccel = accel[:,0]; yaccel = accel[:,1]; zaccel = accel[:,2]
    raw_xpos = cumsum(cumsum(xaccel[start:end]))*T*T
    raw_ypos = cumsum(cumsum(yaccel[start:end]))*T*T
    raw_zpos = cumsum(cumsum(zaccel[start:end]))*T*T

    return raw_xpos, raw_ypos, raw_zpos, g_vector

def compute_diff(impure, imblur, kernel, window=5, zero_thres=10):
    ''' Compute the difference of the two images. The difference will also be
        averaged to reduce the effect of noise.'''
    imreblur = fftconvolve(impure, kernel, mode='same')
    imdiff = abs(imblur - imreblur)**2
    avg_kernel = ones((window, window), dtype=float)/float(window**2)
    x, y = imdiff.shape
    startx = max(0, window//2-1); starty = max(0, window//2-1)
    endx = x + startx; endy = y + starty
    imavg = fftconvolve(imdiff, avg_kernel, mode='full')[startx:endx, starty:endy]
    #imavg = gaussian_filter(imdiff, 4.0, order=0)
    xz, yz = where(imavg <= zero_thres)
    #imavg[xz, yz] = 0

    return imavg, imreblur, xz, yz

def computer_path_diff(im, x, y):
    ''' A very experimental function. We calcluate what we call the path 
        differential of the image, given x vector and y vector.'''
    #Create the basis kernels for a steerable filter.
    sobelx = array([[ 1, 2, 1],
                 [ 0, 0, 0],
                 [-1,-2,-1]])
    sobely = array([[-1, 0, 1],
                 [-2, 0, 2],
                 [-1, 0, 1]])
    dx = x[1:] - x[:-1]
    dy = y[1:] - y[:-1]
    imfinal = zeros_like(im)
    imfinal[:,:] = float("inf")
    for i in range(len(dx)):
        cosx = dx[i]/hypot(dx[i],dy[i])
        sinx = dy[i]/hypot(dx[i],dy[i])
        diff_kernel = sobelx*cosx + sobely*sinx
        imdiff = convolve2d(impure, diff_kernel)[1:-1, 1:-1]
        xmin, ymin = where(imdiff <= imfinal)
        imfinal[xmin, ymin] = imdiff[xmin, ymin]
    imfinal *= 255.0/imfinal.max()
    return imfinal

def compute_var(im, window=5):
    ''' Compute the variance map of the image'''
    var_map = zeros_like(im)
    xdim, ydim = im.shape

    for x in range(0, xdim, window):
        for y in range(0, ydim, window):
            mvar = variance(im[x:x+window, y:y+window])
            var_map[x:x+window, y:y+window] = mvar

    return var_map

def sconv(im, xcoords, ycoords, dmap):
    '''
        Convolve the image using space variant convolution. The xcoords and the 
        ycoords will be scaled by the value of dmap 
    '''
    xdim, ydim = im.shape
    final_im = zeros_like(im)
    avg_map = zeros_like(im)
    w = float(len(xcoords))
    for xidx in range(xdim):
        for yidx in range(ydim):
            # For each pixel, 'Spread' it and add it to the empty image.
            xshifts = xidx + dmap[xidx, yidx]*xcoords
            yshifts = yidx - dmap[xidx, yidx]*ycoords
            illegalx = where((xshifts>=xdim))
            illegaly = where((yshifts>=ydim))
            xshifts[illegalx] = xdim-1; yshifts[illegaly] = ydim-1;
            final_im[xshifts.astype(int), yshifts.astype(int)] += (
                im[xidx, yidx])
            #final_im[xidx, yidx] += (
            #   im[xshifts.astype(int), yshifts.astype(int)]).sum()
            avg_map[xshifts.astype(int), yshifts.astype(int)] += 1
    xz, yz = where(avg_map == 0)
    avg_map[xz, yz] = 1
    return final_im/avg_map

def max_filter(im, w):
    ''' Filter the image using maximum filter'''
    d = w//2
    xdim, ydim = im.shape
    imfiltered = zeros_like(im)
    for x in range(d, xdim-d):
        for y in range(d, ydim-d):
            imfiltered[x-d:x+d, y-d:y+d] = im[x-d:x+d, y-d:y+d].min()
    return imfiltered
    
def mquantize(im, nlevels=5):
    ''' Quantize the image for the given number of levels'''
    vmin = im.min(); vmax = im.max()
    levels = linspace(vmin, vmax, nlevels)
    curr_min = 0
    for level in levels:
        xd, yd = where((im>curr_min) * (im<level))
        im[xd, yd] = curr_min
        curr_min = level
    return im, levels

def linear_convolve(im, kernel):
    ''' Convolve the two images in linear fashion but return only the 
        actual image size
    '''
    imout = fftconvolve(im, kernel, 'full')
    kx, ky = kernel.shape
    xdim, ydim = imout.shape
    if kx%2 == 1:
        kx1, kx2 = kx//2, kx//2
    else:
        kx1 = (kx-1)//2; kx2 = kx//2
    if ky%2 == 1:
        ky1, ky2 = ky//2, ky//2
    else:
        ky1 = (ky-1)//2; ky2 = ky//2
    return imout[kx1:xdim-kx2, ky1:ydim-ky2]

def spacial_fft(im, xw=8, yw=8):
    ''' Compute the spacial fft of the image with given window size'''
    imfft = zeros_like(im, dtype=complex)
    xdim, ydim = im.shape
    for x in range(0, xdim, xw):
        for y in range(0, ydim, yw):
            imfft[x:x+xw, y:y+yw] = fft.fft2(im[x:x+xw, y:y+yw])
    return imfft

def spacial_ifft(im, xw=8, yw=8):
    ''' Compute the spacial ifft of the image with given window size'''
    imifft = zeros_like(im, dtype=complex)
    xdim, ydim = im.shape
    for x in range(0, xdim, xw):
        for y in range(0, ydim, yw):
            imifft[x:x+xw, y:y+yw] = fft.ifft2(im[x:x+xw, y:y+yw])
    return imifft

def spacial_corr(imblur, imreblur, xw=8, yw=8):
    '''Find the correlation map of the two images'''
    IMBLUR = spacial_fft(imblur, xw, yw)
    IMREBLUR = spacial_fft(imreblur, xw, yw)

    IMCORR = IMBLUR*conj(IMREBLUR)/(abs(IMBLUR*IMREBLUR))
    imcorr = spacial_ifft(IMCORR, xw, yw)
    xdim, ydim = imcorr.shape
    for x in range(0, xdim, xw):
        for y in range(0, ydim, yw):
            imcorr[x:x+xw,y:y+yw] = imcorr[x,y]
    return real(imcorr)

def compute_gradient(im1, im2, method='corr', window=5, xw=8, yw=8):
    '''Compute the gradient image for the given two images. As of now, we have
        two modes, corr and diff
    '''
    if method == 'diff':
        avg_kernel = ones((window, window), dtype=float)
        avg_kernel /= avg_kernel.sum()
        diff = fftconvolve(abs(im1 - im2)**2, avg_kernel, mode='same')
        return diff
    elif method == 'corr':
        xdim, ydim = im1.shape
        imcorr = zeros_like(im1)
        for x in range(0, xdim, xw):
            for y in range(0, ydim, yw):
                xcorr = correlate2d(im1[x:x+xw, y:y+yw], 
                                    im2[x:x+xw, y:y+yw], 'valid')
                imcorr[x:x+xw, y:y+yw] = xcorr
        return imcorr

def advanced_iterative_depth(impure, imblur, xpos, ypos):
    ''' 
        Advanced iterative depth estimation. We use a low pass filtering for 
        the 'time' varying pixel signal. The depth is not the point of least
        difference, but the point of smallest diff, smallest absolute first 
        differentiation and largest second differentiation. 
    '''
    imdepth = zeros_like(impure)
    xdim, ydim = impure.shape
    dmax = hypot(xpos, ypos).max()
    # The difference images need to be stacked.
    imdiff = zeros((xdim, ydim, 100))
    # The low pass filter is a simple FIR with 5 taps. 
    lpf = array([-0.00521554, -0.00804016,  0.01335863,  0.10573869,  0.24054812,
        0.30722052,  0.24054812,  0.10573869,  0.01335863, -0.00804016,
       -0.00521554])
    count = 0
    w = 1
    avg_filter = ones((w,w))/(w*w*1.0)
    for depth in linspace(0, 10/dmax, 100):
        print 'Iteration for %d depth'%depth
        kernel = construct_kernel(xpos, ypos, depth)
        imreblur = fftconvolve(impure, kernel, mode='same')
        imsave = fftconvolve(abs(imreblur - imblur)**2, avg_filter, mode='same')
        imdiff[:,:, count] = imsave
        count += 1
    print count
    # Now that we have the stack, we first low pass filter it.
    imdiff = convolve1d(imdiff, lpf, axis=2) 
    # Get the first order and second order differentiations.
    imdiff1 = diff(imdiff, n=1, axis=2); imdiff2 = diff(imdiff, n=2, axis=2)

    # Seems like there is no option but to iterate through each slice.
    plot(imdiff[400,400,:-2])
    show()
    imbest = zeros_like(impure); imbest[:,:] = float('inf')
    imbest1 = zeros_like(impure); imbest2 = zeros_like(impure)
    imbest1[:,:] = float('inf')
    print imdiff.shape, imdiff1.shape, imdiff2.shape
    count = 0
    for count in range(98):
        print 'Estimating depth from %d slice'%count
        #x, y = where( (imdiff[:,:,count] < imbest) & (
        #              imdiff2[:,:,count] > imbest2) )
        x, y = where(imdiff[:,:,count] < imbest)
        imdepth[x, y] = count
        imbest[x, y] = imdiff[x,y,count]
        Image.fromarray(imdepth*255.0/imdepth.max()).convert('RGB').save(
            '../tmp/depth/im%d.bmp'%count)
        #imbest1[x, y] = imdiff1[x, y, count]
        #imbest2[x, y] = imdiff2[x, y, count]
    return imdepth

def patchy_depth(impure, imblur, xpos, ypos, w=31):
    ''' As Prof. ANR suggested, let us check at patches and take that patches
        which has the least error energy
    '''
    dmax = hypot(xpos, ypos).max()
    imdepth = zeros_like(impure)
    xdim, ydim = impure.shape
    nlevels = 40
    d_array = linspace(0, nlevels/dmax, nlevels)
    dstack = []
    # Create blur copies
    for depth in d_array:
        print 'Creating new blur image'
        kernel = construct_kernel(xpos, ypos, depth, 10)
        imreblur = fftconvolve(impure, kernel, mode='same')
        #imreblur = register(imreblur, imblur)
        imdiff = (imreblur - imblur)**2
        dstack.append(imdiff)
    imbest = zeros_like(impure); imbest[:,:] = float('inf')
    for count in range(len(d_array)):
        print 'Estimating new depth'
        for x in range(w, xdim, w):
            for y in range(w, ydim, w):
                if imbest[x:x+w, y:y+w].sum() > dstack[count][x:x+w, y:y+w].sum():
                    imdepth[x:x+w, y:y+w] = count
                    imbest[x:x+w, y:y+w] = dstack[count][x:x+w, y:y+w]
    return imdepth

def norm_diff(im1, im2):
    ''' Difference of two images after normalization'''
    m1 = mean(im1); m2 = mean(im2)
    v1 = variance(im1); v2 = variance(im2)
    imnorm1 = (im1-m1)/sqrt(v1); imnorm2 = (im2-m2)/sqrt(v2)
    diff_im = (imnorm1 - imnorm2)**2
    return diff_im

def fft_diff(im1, im2, w=8):
    ''' Calculate the difference of the two images using spacial fft'''
    IMFFT1 = spacial_fft(im1, w, w)
    IMFFT2 = spacial_fft(im2, w, w)
    IMDIFF = abs(IMFFT1) - abs(IMFFT2)
    imdiff = real(spacial_ifft(IMDIFF, w, w))
    return imdiff

def iterative_depth(impure, imblur, xpos, ypos, mkernel=None):
    ''' Estimate the depth using multiple iterations. Rudimentary, but expected
        to work.
    '''
    w = 7
    avg_filter = ones((w,w))/(w*w*1.0)
    xdim, ydim = impure.shape
    imdepth = zeros((xdim, ydim))
    imdiff = zeros((xdim, ydim)); imdiff[:,:] = float('inf')
    imdiff_curr = zeros((xdim, ydim))
    xw = 32; yw = 32
    dmax = hypot(xpos, ypos).max()
    count = 0
    diff_array1 = []; diff_array2 = []
    nlevels = 25
    save_data = zeros((xdim, ydim, nlevels))
    for depth in linspace(0,1,11):#linspace(0, nlevels/dmax, nlevels):
        print 'Iteration for %f depth'%depth
        if mkernel == None:
            kernel = construct_kernel(xpos, ypos, depth)
        else:
            kernel = zoom(mkernel, depth)
            kernel /= (1e-5+kernel.sum())
        imreblur = linear_convolve(impure, kernel)
        #imreblur = register(imreblur, imblur, kernel)
        # imsave is a 2d image
        imsave = norm_diff(imreblur, imblur)
        imdiff_curr = sqrt(linear_convolve(imsave, avg_filter))
        #imdiff_curr = gaussian_filter(imsave, 3.1)
        #save_data[:,:,count] = imdiff_curr
        imtemp = zeros((xdim, ydim*2), dtype=uint8)
        imtemp[:, :ydim] = imblur
        imtemp[:, ydim:] = imreblur#imsave*255.0/imsave.max()
        Image.fromarray(imtemp).convert('RGB').save(
            '../tmp/depth/im%d.bmp'%count)
        x, y = where(imdiff_curr <= imdiff)
        imdepth[x, y] = depth
        imdiff[x, y] = imdiff_curr[x, y]
        count += 1
    return imdepth, save_data

if __name__ == '__main__':
    try:
        os.mkdir('../tmp/steer')
    except OSError:
        pass
    for idx in [1]:#range(1,7):
        main_dir = '../test_output/depth/case%d'%idx
        #impure = imread(os.path.join(main_dir, 'preview_im.bmp'), flatten=True)
        #imblur = imread(os.path.join(main_dir, 'saved_im.bmp'), flatten=True)
        impure = imread('../test_output/synthetic/case1/preview_im.bmp', flatten=True)
        imblur = imread('../test_output/synthetic/case1/saved_im.bmp', flatten=True)
        #impure = imread('../synthetic/test.jpg', flatten=True)
        #imblur = imread('../tmp/synthetic_blur/space_variant_blur.bmp', flatten=True)


        # Load the acceleration data.
        data = loadtxt(os.path.join(main_dir, 'saved_ac.dat'))
        start = 41
        end = 63
        x, y, z, g = estimate_simple_pos(data, start, end)
        x -= mean(x); y -= mean(y)

        y = range(-4, 5) + [1]*10
        x = linspace(0,1,len(y))

        niters = 10
        window = 4

        impure = register(impure, imblur)
        shifts = range(-2,2,1)
        for xshift in shifts:
            for yshift in shifts:
                print 'Estimating depth for a (%d,%d) shift'%(xshift, yshift)
                imdepth, save_data = iterative_depth(
                    shift(impure, [xshift, yshift]), imblur, x, y)
                imdepth *= 255.0/imdepth.max()
                Image.fromarray(imdepth).convert('RGB').save(
                    '../tmp/steer/%d/depth_%d_%d.bmp'%(idx,xshift,yshift))
                #save('../tmp/diff_data', save_data)
        
    imdepth = 255*imdepth/imdepth.max()
    Image.fromarray(imdepth).show()
    Image.fromarray(imdepth).convert('RGB').save(
        '../tmp/steer/imdepth.bmp')
