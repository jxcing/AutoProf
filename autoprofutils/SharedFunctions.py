import sys
import os
from scipy.integrate import trapz
from scipy.stats import iqr, norm
from scipy.interpolate import interp2d, SmoothBivariateSpline, Rbf, RectBivariateSpline
from scipy.fftpack import fft, ifft
from scipy.optimize import minimize
from scipy.signal import convolve2d
from astropy.visualization import SqrtStretch, LogStretch
from astropy.visualization.mpl_normalize import ImageNormalize
import matplotlib.pyplot as plt
from astropy.io import fits
import numpy as np
from photutils.isophote import EllipseSample, EllipseGeometry, Isophote, IsophoteList
from photutils.isophote import Ellipse as Photutils_Ellipse
import logging
from copy import deepcopy

Abs_Mag_Sun = {'u': 6.39,
               'g': 5.11,
               'r': 4.65,
               'i': 4.53,
               'z': 4.50,
               'U': 6.33,
               'B': 5.31,
               'V': 4.80,
               'R': 4.60,
               'I': 4.51,
               'J': 4.54,
               'H': 4.66,
               'K': 5.08,
               '3.6um': 3.24}     # mips.as.arizona.edu/~cnaw/sun.html # also see: http://www.astronomy.ohio-state.edu/~martini/usefuldata.html
Au_to_Pc    = 4.84814e-6         # pc au^-1
Pc_to_m     = 3.086e16           # m pc^-1
Pc_to_Au    = 206265.            # Au pc^-1


def magperarcsec2_to_mag(mu, a = None, b = None, A = None):
    """
    Converts mag/arcsec^2 to mag
    mu: mag/arcsec^2
    a: semi major axis radius (arcsec)
    b: semi minor axis radius (arcsec)
    A: pre-calculated area (arcsec^2)
    returns: mag
    """
    assert (not A is None) or (not a is None and not b is None)
    if A is None:
        A = np.pi * a * b
    return mu - 2.5*np.log10(A) # https://en.wikipedia.org/wiki/Surface_brightness#Calculating_surface_brightness

def mag_to_magperarcsec2(m, a = None, b = None, R = None, A = None):
    """
    Converts mag to mag/arcsec^2
    m: mag
    a: semi major axis radius (arcsec)
    b: semi minor axis radius (arcsec)
    A: pre-calculated area (arcsec^2)
    returns: mag/arcsec^2
    """
    assert (not A is None) or (not a is None and not b is None) or (not R is None)
    if not R is None:
        A = np.pi * (R**2)
    elif A is None:
        A = np.pi * a * b
    return m + 2.5*np.log10(A) # https://en.wikipedia.org/wiki/Surface_brightness#Calculating_surface_brightness

def halfmag(mag):
    """
    Computes the magnitude corresponding to half in log space.
    Effectively, converts to luminosity, divides by 2, then
    converts back to magnitude. Distance is not needed as it
    cancels out. Here is a basic walk through:
    m_1 - m_ref = -2.5log10(I_1/I_ref)
    m_2 - m_ref = -2.5log10(I_1/2I_ref)
                = -2.5log10(I_1/I_ref) + 2.5log10(2)
    m_2 = m_1 + 2.5log10(2)
    """

    return mag + 2.5 * np.log10(2)

def pc_to_arcsec(R, D, Re = 0.0, De = 0.0):
    """
    Converts a size in parsec to arcseconds

    R: length in pc
    D: distance in pc
    """

    theta = R / (D * Au_to_Pc)
    if np.all(Re == 0) and np.all(De == 0):
        return theta
    else:
        e = theta * np.sqrt((Re/R)**2 + (De/D)**2)
        return theta, e

def arcsec_to_pc(theta, D, thetae = 0.0, De = 0.0):
    """
    Converts a size in arcseconds to parsec

    theta: angle in arcsec
    D: distance in pc
    """
    r = theta * D * Au_to_Pc
    if np.all(thetae == 0) and np.all(De == 0):
        return r
    else:
        e = r * np.sqrt((thetae / theta)**2 + (De / D)**2)
        return r, e

def ISB_to_muSB(I, band, IE = None):
    """
    Converts surface brightness in Lsolar pc^-2 into mag arcsec^-2

    I: surface brightness, (L/Lsun) pc^-2
    band: Photometric band in which measurements were taken
    returns: surface brightness in mag arcsec^-2
    """

    muSB = 21.571 + Abs_Mag_Sun[band] - 2.5 * np.log10(I)
    if IE is None:
        return muSB
    else:
        return muSB, (2.5/np.log(10)) * IE / I

def muSB_to_ISB(mu, band, muE = None):
    """
    Converts surface brightness in mag arcsec^-2 into Lsolar pc^-2

    mu: surface brightness, mag arcsec^-2
    band: Photometric band in which measurements were taken
    returns: surface brightness in (L/Lsun) pc^-2
    """

    ISB = 10**((21.571 + Abs_Mag_Sun[band] - mu)/2.5)
    if muE is None:
        return ISB
    else:
        return ISB, (np.log(10)/2.5) * ISB * muE

def app_mag_to_abs_mag(m, D, me = 0., De = 0.):
    """
    Converts an apparent magnitude to an absolute magnitude
    m: Apparent magnitude
    D: Distance to object in parsecs
    returns: Absolute magnitude at 10 parcecs
    """

    M = m - 5.0 * np.log10(D / 10.0)
    if np.all(me == 0) and np.all(De == 0):
        return M
    else:
        return M, np.sqrt(me**2 + (5. * De / (D * np.log(10)))**2)

def abs_mag_to_app_mag(M, D, Me = 0., De = 0.):
    """
    Converts an absolute magnitude to an apparent magnitude
    M: Absolute magnitude at 10 parcecs
    D: Distance to object in parsecs
    returns: Apparent magnitude
    """

    m = M + 5.0 * np.log10(D / 10.0)
    if np.all(Me == 0) and np.all(De == 0):
        return m
    else:
        return m, np.sqrt(Me**2 + (5. * De / (D * np.log(10)))**2)

    
def mag_to_L(mag, band, mage = None, zeropoint = None):
    """
    Returns the luminosity (in solar luminosities) given the absolute magnitude and reference point.
    mag: Absolute magnitude
    band: Photometric band in which measurements were taken
    mage: uncertainty in absolute magnitude
    zeropoint: user defined zero point
    returns: Luminosity in solar luminosities
    """

    L = 10**(((Abs_Mag_Sun[band] if zeropoint is None else zeropoint) - mag)/2.5)
    if mage is None:
        return L
    else:
        Le = np.abs(L * mage * np.log(10) / 2.5)
        return L, Le

def L_to_mag(L, band, Le = None, zeropoint = None):
    """
    Returns the Absolute magnitude of a star given its luminosity and distance
    L: Luminosity in solar luminosities
    band: Photometric band in which measurements were taken
    Le: Uncertainty in luminosity
    zeropoint: user defined zero point
    
    returns: Absolute magnitude
    """

    mag = (Abs_Mag_Sun[band]if zeropoint is None else zeropoint) - 2.5 * np.log10(L)
    
    if Le is None:
        return mag
    else:
        mage = np.abs(2.5 * Le / (L * np.log(10)))
        return mag, mage

def _iso_extract(IMG, sma, eps, pa, c, more = False):
    """
    Internal, basic function for extracting the pixel fluxes along and isophote
    """
    
    if type(sma) == list:
        box = [[max(0,int(c['x']-max(sma)-2)), min(IMG.shape[0],int(c['x']+max(sma)+2))],
               [max(0,int(c['y']-max(sma)-2)), min(IMG.shape[1],int(c['y']+max(sma)+2))]]
        f_interp = RectBivariateSpline(np.arange(box[1][1] - box[1][0], dtype = np.float32),
                                       np.arange(box[0][1] - box[0][0], dtype = np.float32),
                                       IMG[box[1][0]:box[1][1],box[0][0]:box[0][1]])
        
        N = list(int(np.clip(7*s, a_min = 13, a_max = 50)) for s in sma)
        # points along ellipse to evaluate
        theta = list(np.linspace(0, 2*np.pi - 1./n, n) for n in N)
        # Define ellipse
        X = list(sma[i]*np.cos(theta[i]) for i in range(len(sma)))
        Y = list(sma[i]*(1-eps)*np.sin(theta[i]) for i in range(len(sma)))
        # rotate ellipse by PA
        for i in range(len(sma)):
            X[i],Y[i] = (X[i]*np.cos(pa) - Y[i]*np.sin(pa), X[i]*np.sin(pa) + Y[i]*np.cos(pa))
        theta = list((theta[i] + pa) % (2*np.pi) for i in range(len(sma)))
        flux = list(f_interp(Y[i] + c['y'] - box[1][0],
                             X[i] + c['x'] - box[0][0], grid = False) for i in range(len(sma)))
        if more:
            return flux, theta
        else:
            return flux

    N = int(np.clip(7*sma, a_min = 13, a_max = 50)) if sma < 20 else int(sma*0.5 + 40)
    # points along ellipse to evaluate
    theta = np.linspace(0, 2*np.pi - 1./N, N)
    # Define ellipse
    X = sma*np.cos(theta)
    Y = sma*(1-eps)*np.sin(theta)
    # rotate ellipse by PA
    X,Y = (X*np.cos(pa) - Y*np.sin(pa), X*np.sin(pa) + Y*np.cos(pa))
    theta = (theta + pa) % (2*np.pi)
    
    if sma < 30: 
        box = [[max(0,int(c['x']-sma-2)), min(IMG.shape[0],int(c['x']+sma+2))],
               [max(0,int(c['y']-sma-2)), min(IMG.shape[1],int(c['y']+sma+2))]]
        f_interp = RectBivariateSpline(np.arange(box[1][1] - box[1][0], dtype = np.float32),
                                       np.arange(box[0][1] - box[0][0], dtype = np.float32),
                                       IMG[box[1][0]:box[1][1],box[0][0]:box[0][1]])
        flux = f_interp(Y + c['y'] - box[1][0],
                        X + c['x'] - box[0][0], grid = False)
    else:
        # note uses values at edge when past image boundary, possible fixme?
        flux = IMG[np.clip(np.rint(Y + c['y']), a_min = 0, a_max = IMG.shape[0]-1).astype(int),
                   np.clip(np.rint(X + c['x']), a_min = 0, a_max = IMG.shape[1]-1).astype(int)]
    if more:
        return flux, theta
    else:
        return flux

def _sampleflux(x, dat):
    f_interp = RectBivariateSpline(np.arange(dat.shape[0], dtype = np.float32),
                                   np.arange(dat.shape[1], dtype = np.float32),
                                   dat)
    return f_interp(x[1], x[0], grid = False)
    
def _GaussFit(x, sr, sf):
    return np.mean((sf - (x[1]*norm.pdf(sr, loc = 0, scale = x[0])))**2)

def StarFind(IMG, fwhm_guess, background_noise, mask = None, peakmax = None, detect_threshold = 20., minsep = 10., reject_size = 10., maxstars = np.inf):
    """
    Find stars in an image, determine their fwhm and peak flux values.

    IMG: image data as numpy 2D array
    fwhm_guess: A guess at the PSF fwhm, can be within a factor of 2 and everything should work
    background_noise: image background flux noise
    mask: masked pixels as numpy 2D array with same dimensions as IMG
    peakmax: maximum allowed peak flux value for a star, used to remove saturated pixels
    detect_threshold: threshold (in units of sigma) value for convolved image to consider a pixel as a star candidate.
    minsep: minimum allowed separation between stars, in units of fwhm_guess
    reject_size: reject stars with fitted FWHM greater than this times the fwhm_guess
    maxstars: stop once this number of stars have been found, this is for speed purposes
    """

    # Convolve edge detector with image
    zz = np.ones((9,9))*-1
    zz[3:6,3:6] = 8
    new = convolve2d(IMG, zz, mode = 'same')

    centers = []
    fwhms = []
    peaks = []

    # Select pixels which edge detector identifies
    if mask is None:
        highpixels = np.argwhere(new > detect_threshold*iqr(new))
    else:
        highpixels = np.argwhere(np.logical_and(new > detect_threshold*iqr(new),
                                                np.logical_not(mask)))

    # Meshgrid for performing flux center-of-mass calculation
    # N = 4
    # xx, yy = np.meshgrid(np.arange(N,dtype=float), np.arange(N,dtype=float), indexing = 'ij')
    
    for i in range(len(highpixels)):
        # reject if near an existing center
        if len(centers) != 0 and np.any(np.sqrt(np.sum((highpixels[i] - centers)**2,axis = 1)) < minsep*fwhm_guess):
            continue
        # reject if near edge
        if np.any(highpixels[i] < 5*fwhm_guess) or np.any(highpixels[i] > (np.array(IMG.shape) - 5*fwhm_guess)):
            continue
        # set starting point at local maximum pixel
        newcenter = np.array([highpixels[i][1],highpixels[i][0]])
        ranges = [[max(0,int(newcenter[0]-fwhm_guess*5)), min(IMG.shape[1],int(newcenter[0]+fwhm_guess*5))],
                  [max(0,int(newcenter[1]-fwhm_guess*5)), min(IMG.shape[0],int(newcenter[1]+fwhm_guess*5))]]
        newcenter = np.unravel_index(np.argmax(IMG[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]].T),IMG[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]].T.shape) + np.array([ranges[0][0],ranges[1][0]])
        if np.any(newcenter < 5*fwhm_guess) or np.any(newcenter > (np.array(IMG.shape) - 5*fwhm_guess)):
            continue
        # count = 0
        # while count < 25:
        #     count += 1
        #     chunk = IMG[int(newcenter[1]-N/2):int(newcenter[1]+N/2),int(newcenter[0]-N/2):int(newcenter[0]+N/2)]
        #     M = np.sum(chunk)
        #     newx = int(newcenter[0]-N/2) + np.sum(chunk*yy)/M
        #     newy = int(newcenter[1]-N/2) + np.sum(chunk*xx)/M
        #     if abs(newx - newcenter[0]) < 0.1 and abs(newy - newcenter[1]) < 0.1:
        #         break
        #     newcenter = np.array([newx,newy])
        #     if np.any(newcenter < minsep*fwhm_guess) or np.any(newcenter > (np.array(IMG.shape) - minsep*fwhm_guess)):
        #         count = 40
        #         break
        # if count >= 25:
        #     continue
        com_center = deepcopy(newcenter)
        ranges = [[max(0,int(newcenter[0]-fwhm_guess)), min(IMG.shape[1],int(newcenter[0]+fwhm_guess))],
                  [max(0,int(newcenter[1]-fwhm_guess)), min(IMG.shape[0],int(newcenter[1]+fwhm_guess))]]
        chunk = IMG[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]]
        f_interp = RectBivariateSpline(np.arange(chunk.shape[0], dtype = np.float32),
                                       np.arange(chunk.shape[1], dtype = np.float32),
                                       chunk)
        newcenter = minimize(lambda x,d: -f_interp(x[1], x[0], grid = False), x0 = newcenter - np.array([ranges[0][0],ranges[1][0]]),
                             args = (IMG[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]],)).x # , method = 'Nelder-Mead'
        newcenter += np.array([ranges[0][0],ranges[1][0]])
        #logging.info('bicubic update by: %s, from com %s, to bicubic %s, highpixel %s' % (str(com_center - newcenter), str(com_center), str(newcenter), str(highpixels[i])))
        if np.any(newcenter < 5*fwhm_guess) or np.any(newcenter > (np.array(IMG.shape) - 5*fwhm_guess)):
            continue
        if (not peakmax is None) and np.any(IMG[int(newcenter[1]-minsep*fwhm_guess):int(newcenter[1]+minsep*fwhm_guess),
                                                int(newcenter[0]-minsep*fwhm_guess):int(newcenter[0]+minsep*fwhm_guess)] >= peakmax):
            continue
        if len(centers) != 0 and np.any(np.sqrt(np.sum((newcenter - centers)**2,axis = 1)) < minsep*fwhm_guess):
            continue

        isovals = _iso_extract(IMG, fwhm_guess, 0., 0., {'x': newcenter[0], 'y': newcenter[1]})
        coefs = fft(isovals)
        if np.sum(np.abs(coefs[1:5])) > np.sqrt(np.abs(coefs[0])):
            continue
        flux = [np.median(_iso_extract(IMG, 0.0, 0., 0., {'x': newcenter[0], 'y': newcenter[1]}))]
        R = [0.5]
        badcount = 0
        while flux[-1] > (flux[0]/2): #len(R) < 50 and (flux[-1] > background_noise or len(R) <= 5):
            R.append(R[-1]*(1.1))
            isovals = _iso_extract(IMG, R[-1], 0., 0., {'x': newcenter[0], 'y': newcenter[1]})
            coefs = fft(isovals)
            if np.sum(np.abs(coefs[1:5])) > np.sqrt(np.abs(coefs[0])):
                badcount += 1
            flux.append(np.median(isovals))
            #plt.scatter(R[-1]*np.ones(len(isovals)), isovals, color = 'r') # fixme
        if badcount > 1:
            #plt.clf() # fixme
            continue
        # res = minimize(_GaussFit, x0 = [fwhm_guess/2.355, flux[0]/norm.pdf(0,loc = 0,scale = fwhm_guess/2.355)], args = (np.array(R), np.array(flux)), method = 'Nelder-Mead')
        # if not res.success or res.x[0]*2.355 > reject_size*fwhm_guess:
        #     #plt.clf() # fixme
        #     continue
        if len(centers) == 0:
            centers = np.array([deepcopy(newcenter)])
        else:
            centers = np.concatenate((centers,[newcenter]),axis = 0)
        fwhms.append(np.interp(flux[0]/2, flux[-3:], R[-3:])*2)#(res.x[0]*2.355)
        peaks.append(flux[0])#(res.x[1] / norm.pdf(0,loc = 0,scale = res.x[0]))
        if len(fwhms) >= maxstars:
            break
        # randid = np.random.randint(10000)
        # plt.scatter(R, flux, color = 'b')
        # plt.plot(R, res.x[1]*norm.pdf(R,loc = 0, scale = res.x[0]), color = 'g')
        # plt.savefig('test/PSF_test_%i_fit.jpg' % randid)
        # plt.clf()

        # ranges = [[max(0,int(newcenter[0]-fwhm_guess*5)), min(IMG.shape[1],int(newcenter[0]+fwhm_guess*5))],
        #           [max(0,int(newcenter[1]-fwhm_guess*5)), min(IMG.shape[0],int(newcenter[1]+fwhm_guess*5))]]
        # plt.imshow(np.clip(IMG[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]],
        #                    a_min = 0,a_max = None), origin = 'lower', cmap = 'Greys_r', norm = ImageNormalize(stretch=LogStretch()))
        # plt.scatter([newcenter[0] - ranges[0][0]], [newcenter[1] - ranges[1][0]], color = 'r', marker = 'x')
        # plt.scatter([com_center[0] - ranges[0][0]], [com_center[1] - ranges[1][0]], color = 'b', marker = 'x')
        # plt.scatter([highpixels[i][1] - ranges[0][0]], [highpixels[i][0] - ranges[1][0]], color = 'g', marker = 'x')
        # plt.savefig('test/PSF_test_%i_center.jpg' % randid)
        # plt.clf()
        
    logging.info('fwhm mean %f, median %f, std %f, len %i' % (np.mean(fwhms), np.median(fwhms), np.std(fwhms), len(fwhms)))
    return {'x': centers[:,0], 'y': centers[:,1], 'fwhm': np.array(fwhms), 'peak': np.array(peaks)}



def _x_to_pa(x):
    """
    Internal, basic function to ensure position angles remain
    in the proper parameter space (0, pi)
    """
    return x % np.pi #np.pi / (1. + np.exp(-(x-np.pi/2)))
def _inv_x_to_pa(pa):
    """
    Internal, reverse _x_to_pa, although this is just a filler
    function as _x_to_pa is non reversible.
    """
    return pa % np.pi
#
def _x_to_eps(x):
    """
    Internal, function to map the reals to the range (0.05,0.95)
    as the range of reasonable ellipticity values.
    """
    return 0.02 + 0.96*(0.5 + np.arctan(x-0.5)/np.pi) #0.02 + 0.96/(1. + np.exp(-(x - 0.5))) 
#
def _inv_x_to_eps(eps):
    """
    Internal, inverse of _x_to_eps function
    """
    return 0.5 + np.tan(np.pi*((eps - 0.02)/0.96 - 0.5)) #0.5 - np.log(0.96/(eps - 0.02) - 1.) 


def Read_Image(filename, **kwargs):
    """
    Reads a galaxy image given a file name. In a fits image the data is assumed to exist in the
    primary HDU unless given 'hdulelement'. In a numpy file, it is assumed that only one image
    is in the file.
    
    filename: A string containing the full path to an image file

    returns: Extracted image data as numpy 2D array
    """

    # Read a fits file
    if filename[filename.rfind('.')+1:].lower() == 'fits':
        hdul = fits.open(filename)
        dat = hdul[kwargs['hdulelement'] if 'hdulelement' in kwargs else 0].data
    # Read a numpy array file
    if filename[filename.rfind('.')+1:].lower() == 'npy':
        dat = np.load(filename)
            
    return dat

def Angle_TwoAngles(a1, a2):
    """
    Compute the angle between two vectors at angles a1 and a2
    """

    return np.arccos(np.sin(a1)*np.sin(a2) + np.cos(a1)*np.cos(a2))
    

def Angle_Average(a):
    """
    Compute the average for a list of angles, which may wrap around a cyclic boundary.

    a: list of angles in the range [0,2pi]
    """
    i = np.cos(a) + 1j*np.sin(a)
    return np.angle(np.mean(i))

def Angle_Scatter(a):
    """
    Compute the average for a list of angles, which may wrap around a cyclic boundary.

    a: list of angles in the range [0,2pi]
    """
    i = np.cos(a) + 1j*np.sin(a)
    return iqr(np.angle(1j*i/np.mean(i)),rng = [16,84])


def GetKwargs(c):

    newkwargs = {}

    try:
        newkwargs['saveto'] = c.saveto
    except:
        newkwargs['saveto'] = None
    try:
        newkwargs['name'] = c.name
    except:
        newkwargs['name'] = None
    try:
        newkwargs['n_procs'] = c.n_procs
    except:
        newkwargs['n_procs'] = 1
    try:
        newkwargs['mask_file'] = c.mask_file
    except:
        newkwargs['mask_file'] = None
    try:
        newkwargs['savemask'] = c.savemask
    except:
        pass
    try:
        newkwargs['psf_guess'] = c.psf_guess
    except:
        pass
    try:
        newkwargs['psf_set'] = c.psf_set
    except:
        pass
    try:
        newkwargs['autodetectoverflow'] = c.autodetectoverflow
    except:
        pass
    try:
        newkwargs['overflowval'] = c.overflowval
    except:
        pass
    try:
        newkwargs['forcing_profile'] = c.forcing_profile
    except:
        pass
    try:
        newkwargs['plotpath'] = c.plotpath
    except:
        pass
    try:
        newkwargs['doplot'] = c.doplot
    except:
        pass
    try:
        newkwargs['hdulelement'] = c.hdulelement
    except:
        pass
    try:
        newkwargs['given_center'] = c.given_center
    except:
        pass
    try:
        newkwargs['scale'] = c.scale
    except:
        pass
    try:
        newkwargs['samplegeometricscale'] = c.samplegeometricscale
    except:
        pass
    try:
        newkwargs['samplelinearscale'] = c.samplelinearscale
    except:
        pass
    try:
        newkwargs['samplestyle'] = c.samplestyle
    except:
        pass
    try:
        newkwargs['sampleinitR'] = c.sampleinitR
    except:
        pass
    try:
        newkwargs['sampleendR'] = c.sampleendR
    except:
        pass
    try:
        newkwargs['sampleerrorlim'] = c.sampleerrorlim
    except:
        pass
    try:
        newkwargs['zeropoint'] = c.zeropoint
    except:
        pass
    return newkwargs



def SBprof_to_COG(R, SB, axisratio, method = 0):
    """
    Converts a surface brightness profile to a curve of growth by integrating
    the SB profile in flux units then converting back to mag units. Two methods
    are implemented, one using the trapezoid method and one assuming constant
    SB between isophotes. Trapezoid method is in principle more accurate, but
    may become unstable with erratic data.

    R: Radius in arcsec
    SB: surface brightness in mag arcsec^-2
    axisratio: b/a indicating degree of isophote ellipticity
    method: 0 for trapezoid, 1 for constant

    returns: magnitude values at each radius of the profile in mag
    """
    
    m = np.zeros(len(R))
    # Dummy band for conversions, cancelled out on return
    band = 'r'

    # Method 0 uses trapezoid method to integrate in flux space
    if method == 0:
        # Compute the starting point assuming constant SB within first isophote
        m[0] = magperarcsec2_to_mag(SB[0], A = np.pi*axisratio[0]*(R[0]**2))
        # Dummy distance value for integral
        D = 10
        # Convert to flux space
        I = muSB_to_ISB(np.array(SB), band)
        # Ensure numpy array
        axisratio = np.array(axisratio)
        # Convert to physical radius using dummy distance
        R = arcsec_to_pc(np.array(R), D)
        # Integrate up to each radius in the profile
        for i in range(1,len(R)):
            m[i] = abs_mag_to_app_mag(L_to_mag(trapz(2*np.pi*I[:i+1]*R[:i+1]*axisratio[:i+1],R[:i+1]) + \
                                               mag_to_L(app_mag_to_abs_mag(m[0], D), band), band),D)
    elif method == 1:
        # Compute the starting point assuming constant SB within first isophote
        m[0] = magperarcsec2_to_mag(SB[0], A = np.pi*axisratio[0]*(R[0]**2))
        # Progress through each radius and add the contribution from each isophote individually
        for i in range(1,len(R)):
            m[i] = L_to_mag(mag_to_L(magperarcsec2_to_mag(SB[i], A = np.pi*axisratio[i]*(R[i]**2)), band) - \
                            mag_to_L(magperarcsec2_to_mag(SB[i], A = np.pi*axisratio[i-1]*(R[i-1]**2)), band) + \
                            mag_to_L(m[i-1], band), band)

    return m


def SBprof_to_COG_errorprop(R, SB, SBE, axisratio, axisratioE = None, N = 100, method = 0, symmetric_error = True):
    """
    Converts a surface brightness profile to a curve of growth by integrating
    the SB profile in flux units then converting back to mag units. Two methods
    are implemented, one using the trapezoid method and one assuming constant
    SB between isophotes. Trapezoid method is in principle more accurate, but
    may become unstable with erratic data. An uncertainty profile is also
    computed, from a given SB uncertainty profile and optional axisratio
    uncertainty profile.
    
    R: Radius in arcsec
    SB: surface brightness in mag arcsec^-2
    SBE: surface brightness uncertainty relative mag arcsec^-2
    axisratio: b/a indicating degree of isophote ellipticity
    axisratioE: uncertainty in b/a
    N: number of iterations for computing uncertainty
    method: 0 for trapezoid, 1 for constant
    
    returns: magnitude and uncertainty profile in mag
    """

    # If not provided, axis ratio error is assumed to be zero
    if axisratioE is None:
        axisratioE = np.zeros(len(R))
        
    # Create container for the monte-carlo iterations
    COG_results = np.zeros((N, len(R))) + 99.999
    SB_CHOOSE = np.logical_and(np.isfinite(SB), SB < 50)
    if np.sum(SB_CHOOSE) < 5:
        return (None, None) if symmetric_error else (None, None, None)
    COG_results[0][SB_CHOOSE] = SBprof_to_COG(R[SB_CHOOSE], SB[SB_CHOOSE], axisratio[SB_CHOOSE], method = method)
    for i in range(1,N):
        # Randomly sampled SB profile
        tempSB = np.random.normal(loc = SB, scale = SBE)
        # Randomly sampled axis ratio profile
        tempq = np.random.normal(loc = axisratio, scale = axisratioE)
        # Compute COG with sampled data
        COG_results[i][SB_CHOOSE] = SBprof_to_COG(R[SB_CHOOSE], tempSB[SB_CHOOSE], tempq[SB_CHOOSE], method = method)

    # Condense monte-carlo evaluations into profile and uncertainty envelope
    COG_profile = COG_results[0]
    COG_lower = np.median(COG_results, axis = 0) - np.quantile(COG_results, 0.317310507863/2, axis = 0)
    COG_upper = np.quantile(COG_results, 1. - 0.317310507863/2, axis = 0) - np.median(COG_results, axis = 0)

    # Return requested uncertainty format
    if symmetric_error:
        return COG_profile, np.abs(COG_lower + COG_upper)/2
    else:
        return COG_profile, COG_lower, COG_upper
    
