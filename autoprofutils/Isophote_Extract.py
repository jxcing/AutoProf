import numpy as np
from photutils.isophote import EllipseSample, Ellipse, EllipseGeometry, Isophote, IsophoteList
from scipy.optimize import minimize
from scipy.stats import iqr
from time import time
from astropy.visualization import SqrtStretch, LogStretch
from astropy.visualization.mpl_normalize import ImageNormalize
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from copy import copy
import logging
import sys
import os
sys.path.append(os.environ['AUTOPROF'])
from autoprofutils.SharedFunctions import _x_to_pa, _x_to_eps, _inv_x_to_eps, _inv_x_to_pa, SBprof_to_COG_errorprop

def Simple_Isophote_Extract(IMG, mask, background_level, center, R, E, PA, name = ''):
    """
    Extracts the specified isophotes using photutils ellipsesample function.
    Applies mask and backgorund level to image.    
    """

    # Create image array with background and mask applied
    if np.any(mask):
        logging.info('%s: is masked' % (name))
        dat = np.ma.masked_array(IMG - background_level, mask)
    else:
        logging.info('%s: is not masked' % (name))
        dat = IMG - background_level

    # Store isophotes
    iso_list = []
    
    for i in range(len(R)):
        # Container for ellipse geometry
        geo = EllipseGeometry(sma = R[i],
                              x0 = center['x'], y0 = center['y'],
                              eps = E[i], pa = PA[i])
        # Extract the isophote information
        ES = EllipseSample(dat, sma = R[i], geometry = geo)
        ES.extract()
        iso_list.append(Isophote(ES, niter = 30, valid = True, stop_code = 0))
        
    return IsophoteList(iso_list)

def Generate_Profile(IMG, pixscale, mask, background, center, R, E, PA, name):    

    isolist =  Simple_Isophote_Extract(IMG, mask, background,
                                       center, R, E, PA, name)
    
    # Compute surface brightness in mag arcsec^-2 from flux

    sb = np.array(list((-2.5*np.log10(np.median(isolist.sample[i].values[2]))\
                        + 22.5 + 2.5*np.log10(pixscale**2)) \
                       for i in range(len(isolist.sma))))
    sb[np.logical_not(np.isfinite(sb))] = 99.999

    sbE = list((iqr(isolist.sample[i].values[2],
                    rng = (31.7310507863/2,
                           100 - 31.7310507863/2)) / (2*np.sqrt(len(isolist.sample[i].values[2])))) \
               for i in range(len(isolist.sma)))

    sbE = np.array(list((np.abs(2.5*sbE[i]/(np.median(isolist.sample[i].values[2]) * np.log(10)))) \
                        for i in range(len(isolist.sma))))

    sb[np.logical_not(np.isfinite(sbE))] = 99.999
    sbE[np.logical_not(np.isfinite(sbE))] = 99.999

    # Compute Curve of Growth from SB profile
    cog, cogE = SBprof_to_COG_errorprop(isolist.sma * pixscale, sb, sbE, 1. - isolist.eps,
                                        isolist.ellip_err, N = 100, method = 0, symmetric_error = True)
    if cog is None:
        logging.error('%s: Photometry failed, SB profile is nans or all > 50' % str(name))
        return

    # For each radius evaluation, write the profile parameters
    params = ['R', 'SB', 'SB_e', 'totmag', 'totmag_e', 'ellip', 'ellip_e', 'pa', 'pa_e', 'totmag_direct', 'totmag_direct_e'] # , 'x0', 'y0'
    
    SBprof_data = dict((h,[]) for h in params)
    SBprof_units = {'R': 'arcsec', 'SB': 'mag arcsec^-2', 'SB_e': 'mag arcsec^-2', 'totmag': 'mag', 'totmag_e': 'mag',
                    'ellip': 'unitless', 'ellip_e': 'unitless', 'pa': 'deg', 'pa_e': 'deg', 'totmag_direct': 'mag', 'totmag_direct_e': 'mag'}#,'x0': 'pix', 'y0': 'pix'
    SBprof_format = {'R': '%.4f', 'SB': '%.4f', 'SB_e': '%.4f', 'totmag': '%.4f', 'totmag_e': '%.4f',
                    'ellip': '%.3f', 'ellip_e': '%.3f', 'pa': '%.2f', 'pa_e': '%.2f', 'totmag_direct': '%.4f', 'totmag_direct_e': '%.4f'} #,'x0': '%.1f', 'y0': '%.1f'
    for i in range(len(isolist.sma)):
        tflux_e_err = isolist.rms[i] / (np.sqrt(isolist.npix_e[i]))
        SBprof_data['R'].append(isolist.sma[i] * pixscale)
        SBprof_data['SB'].append(sb[i])
        SBprof_data['SB_e'].append(sbE[i])
        SBprof_data['totmag'].append(cog[i])
        SBprof_data['totmag_e'].append(cogE[i])
        SBprof_data['ellip'].append(isolist.eps[i])
        SBprof_data['ellip_e'].append(isolist.ellip_err[i])
        SBprof_data['pa'].append(isolist.pa[i]*180/np.pi)
        SBprof_data['pa_e'].append(isolist.pa_err[i]*180/np.pi)
        SBprof_data['totmag_direct'].append(22.5 - 2.5*np.log10(isolist.tflux_e[i]))
        SBprof_data['totmag_direct_e'].append(np.abs(2.5*tflux_e_err/(isolist.tflux_e[i] * np.log(10))))
        # SBprof_data['x0'].append(isolist.x0[i])
        # SBprof_data['y0'].append(isolist.y0[i])

    return {'header': params, 'units': SBprof_units, 'data': SBprof_data, 'format': SBprof_format}

def Isophote_Extract_Forced(IMG, pixscale, name, results, **kwargs):

    with open(kwargs['forcing_profile'], 'r') as f:
        raw = f.readlines()
        for i,l in enumerate(raw):
            if l[0] != '#':
                readfrom = i
                break
        header = list(h.strip() for h in raw[readfrom].split(','))
        force = dict((h,[]) for h in header)
        for l in raw[readfrom+2:]:
            for d, h in zip(l.split(','), header):
                force[h].append(float(d.strip()))

    
    return Generate_Profile(IMG, pixscale, np.logical_or(results['starmask']['overflow mask'],results['starmask']['mask']),
                            results['background']['median'], results['center'], np.array(force['R'])/pixscale, force['ellip'],
                            np.array(force['pa'])*np.pi/180, name)

def Isophote_Extract(IMG, pixscale, name, results, **kwargs):
    """
    Extract isophotes given output profile from Isophotes_Simultaneous_Fit which
    parametrizes pa and ellipticity via functions which map all the reals to the
    appropriate parameter range. This function also extrapolates the profile to
    large and small radii (simply by taking the parameters at the edge, no
    functional extrapolation). By default uses a linear radius growth, however
    for large images, it uses a geometric radius growth of 10% per isophote.
    """

    if 'center' in results['isophotefit']:
        use_center = results['isophotefit']['center']
    else:
        use_center = results['center']
        
    # Radius values to evaluate isophotes
    R = [kwargs['sampleinitR'] if 'sampleinitR' in kwargs else min(1.,results['psf']['median']/2)]
    while ((R[-1] < kwargs['sampleendR'] if 'sampleendR' in kwargs else True) and R[-1] < 2*results['isophotefit']['R'][-1] and R[-1] < min(IMG.shape)/2) or (kwargs['extractfull'] if 'extractfull' in kwargs else False):
        if 'samplestyle' in kwargs and kwargs['samplestyle'] == 'geometric-linear':
            if len(R) > 1 and abs(R[-1] - R[-2]) >= (kwargs['samplelinearscale'] if 'samplelinearscale' in kwargs else 3*results['psf']['median']):
                R.append(R[-1] + (kwargs['samplelinearscale'] if 'samplelinearscale' in kwargs else results['psf']['median']))
            else:
                R.append(R[-1]*(1. + (kwargs['samplegeometricscale'] if 'samplegeometricscale' in kwargs else 0.1)))
        elif 'samplestyle' in kwargs and kwargs['samplestyle'] == 'linear':
            R.append(R[-1] + (kwargs['samplelinearscale'] if 'samplelinearscale' in kwargs else 0.5*results['psf']['median']))
        else:
            R.append(R[-1]*(1. + (kwargs['samplegeometricscale'] if 'samplegeometricscale' in kwargs else 0.1)))
    R = np.array(R)
    logging.info('%s: R complete in range [%.1f,%.1f]' % (name,R[0],R[-1]))
    
    # Interpolate profile values, when extrapolating just take last point
    E = _x_to_eps(np.interp(R, results['isophotefit']['R'], _inv_x_to_eps(results['isophotefit']['ellip'])))
    E[R < results['isophotefit']['R'][0]] = R[R < results['isophotefit']['R'][0]] * results['isophotefit']['ellip'][0] / results['isophotefit']['R'][0]
    E[R > results['isophotefit']['R'][-1]] = results['isophotefit']['ellip'][-1]
    tmp_pa_s = np.interp(R, results['isophotefit']['R'], np.sin(2*results['isophotefit']['pa']))
    tmp_pa_c = np.interp(R, results['isophotefit']['R'], np.cos(2*results['isophotefit']['pa']))
    PA = _x_to_pa(((np.arctan(tmp_pa_s/tmp_pa_c) + (np.pi*(tmp_pa_c < 0))) % (2*np.pi))/2)#_x_to_pa(np.interp(R, results['isophotefit']['R'], results['isophotefit']['pa']))
    PA[R < results['isophotefit']['R'][0]] = _x_to_pa(results['isophotefit']['pa'][0])
    PA[R > results['isophotefit']['R'][-1]] = _x_to_pa(results['isophotefit']['pa'][-1])

    # Stop from masking anything at the center
    results['starmask']['mask'][int(use_center['x'] - 10*results['psf']['median']):int(use_center['x'] + 10*results['psf']['median']),
                            int(use_center['y'] - 10*results['psf']['median']):int(use_center['y'] + 10*results['psf']['median'])] = False
    compund_Mask = np.logical_or(results['starmask']['overflow mask'],results['starmask']['mask'])

    # Extract SB profile
    return Generate_Profile(IMG,pixscale,compund_Mask,
                            results['background']['median'],
                            use_center,
                            R, E, PA, name)
