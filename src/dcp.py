import math
import os

import cv2
import numpy as np
from matplotlib import pyplot as plt
from PIL import Image


def DarkChannel(im,sz):
    b,g,r = cv2.split(im)
    dc = cv2.min(cv2.min(r,g),b)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(sz,sz))
    dark = cv2.erode(dc,kernel)
    return dark

def AtmLight(im,dark):
    [h,w] = im.shape[:2]
    imsz = h*w
    numpx = int(max(math.floor(imsz/1000),1))
    darkvec = dark.reshape(imsz)
    imvec = im.reshape(imsz,3)

    indices = darkvec.argsort()
    indices = indices[imsz-numpx::]

    atmsum = np.zeros([1,3])
    for ind in range(1,numpx):
       atmsum = atmsum + imvec[indices[ind]]

    A = atmsum / numpx
    return A

def TransmissionEstimate(im,A,sz):
    omega = 0.95
    im3 = np.empty(im.shape,im.dtype)

    for ind in range(0,3):
        im3[:,:,ind] = im[:,:,ind]/A[0,ind]

    transmission = 1 - omega*DarkChannel(im3,sz)
    return transmission

def Guidedfilter(im,p,r,eps):
    mean_I = cv2.boxFilter(im,cv2.CV_64F,(r,r))
    mean_p = cv2.boxFilter(p, cv2.CV_64F,(r,r))
    mean_Ip = cv2.boxFilter(im*p,cv2.CV_64F,(r,r))
    cov_Ip = mean_Ip - mean_I*mean_p

    mean_II = cv2.boxFilter(im*im,cv2.CV_64F,(r,r))
    var_I   = mean_II - mean_I*mean_I

    a = cov_Ip/(var_I + eps)
    b = mean_p - a*mean_I

    mean_a = cv2.boxFilter(a,cv2.CV_64F,(r,r))
    mean_b = cv2.boxFilter(b,cv2.CV_64F,(r,r))

    q = mean_a*im + mean_b
    return q

def TransmissionRefine(im,et):
    gray = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    gray = np.float64(gray)/255
    r = 60
    eps = 0.0001
    t = Guidedfilter(gray,et,r,eps)

    return t

def Recover(im,t,A,tx = 0.1):
    res = np.empty(im.shape,im.dtype)
    t = cv2.max(t,tx)

    for ind in range(0,3):
        res[:,:,ind] = (im[:,:,ind]-A[0,ind])/t + A[0,ind]

    return res

def makeDensityMask(img):
    """_summary_

    Args:
        img (numpy.ndarray) : [H, W, 3] (0 ~ 255)

    Returns:
        mask (numpy.ndarray) : [H, W, 1] (0 ~ 1)
    """
    I = img / 255.0
    dark = DarkChannel(I, 15)
    A = AtmLight(I, dark)
    t1 = TransmissionEstimate(I, A, 15)
    t2 = TransmissionRefine((I * 255.0).astype('float32'), t1)
    density_map = 1 - t2
    density_map = density_map[:, :, np.newaxis] 
    return density_map

if __name__ == '__main__':
    import sys
    try:
        fn = sys.argv[1]
    except:
        fn = 'NH_Haze/train/hazy/01_hazy.png'

    def nothing(*argv):
        pass
    src = Image.open(fn).convert('RGB')
    I = np.asarray(src, np.float64)
    I = I / 255.0
    
    dark = DarkChannel(I, 15)
    A = AtmLight(I, dark)
    t1 = TransmissionEstimate(I, A, 15)
    t2 = TransmissionRefine((I * 255.0).astype('float32'), t1)
    density_map = 1 - t2
    J = Recover(I, t2, A, 0.1)
    
    density_map = np.clip(density_map * 255.0, 0, 255)
    density_map = density_map.astype(np.uint8)
    
    density_map = Image.fromarray(density_map)
    density_map.save(os.getcwd() + '/density_map.png')