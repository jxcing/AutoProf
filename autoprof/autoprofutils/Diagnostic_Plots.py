import numpy as np
from astropy.visualization import SqrtStretch, LogStretch
from astropy.visualization.mpl_normalize import ImageNormalize
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Wedge
import matplotlib.cm as cm
import matplotlib
from itertools import compress
import sys
import os
sys.path.append(os.environ['AUTOPROF'])
from autoprofutils.SharedFunctions import _x_to_pa, _x_to_eps, _inv_x_to_eps, _inv_x_to_pa, LSBImage, AddLogo, _average, _scatter, flux_to_sb, flux_to_mag, PA_shift_convention, autocolours, autocmap, fluxdens_to_fluxsum_errorprop, mag_to_flux

def Plot_Background(values, bkgrnd, noise, results, options):

    hist, bins = np.histogram(values[np.logical_and((values-bkgrnd) < 20*noise, (values-bkgrnd) > -5*noise)], bins = max(10,int(np.sqrt(len(values))/2)))
    plt.figure(figsize = (5,5))
    plt.bar(bins[:-1], np.log10(hist), width = bins[1] - bins[0], color = 'k', label = 'pixel values')
    plt.axvline(bkgrnd, color = '#84DCCF', label = 'sky level: %.5e' % bkgrnd)
    plt.axvline(bkgrnd - noise, color = '#84DCCF', linewidth = 0.7, linestyle = '--', label = '1$\\sigma$ noise/pix: %.5e' % noise)
    plt.axvline(bkgrnd + noise, color = '#84DCCF', linewidth = 0.7, linestyle = '--')
    plt.xlim([bkgrnd-5*noise, bkgrnd+20*noise])
    plt.legend(fontsize = 12)
    plt.tick_params(labelsize = 12)
    plt.xlabel('Pixel Flux', fontsize = 16)
    plt.ylabel('log$_{10}$(count)', fontsize = 16)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'Background_hist_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()        

def Plot_PSF_Stars(IMG, stars_x, stars_y, stars_fwhm, psf, results, options, flagstars = None):
    LSBImage(IMG - results['background'], results['background noise'])
    for i in range(len(stars_fwhm)):
        plt.gca().add_patch(Ellipse((stars_x[i],stars_y[i]), 20*psf, 20*psf,
                                    0, fill = False, linewidth = 1.5, color = autocolours['red1'] if not flagstars is None and flagstars[i] else autocolours['blue1']))
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'PSF_Stars_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()


def Plot_Isophote_Init_Ellipse(dat, circ_ellipse_radii, ellip, phase, results, options):
    ranges = [[max(0,int(results['center']['x']-circ_ellipse_radii[-1]*1.5)), min(dat.shape[1],int(results['center']['x']+circ_ellipse_radii[-1]*1.5))],
              [max(0,int(results['center']['y']-circ_ellipse_radii[-1]*1.5)), min(dat.shape[0],int(results['center']['y']+circ_ellipse_radii[-1]*1.5))]]
        
    LSBImage(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]], results['background noise'])
    # plt.imshow(np.clip(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]],a_min = 0, a_max = None),
    #            origin = 'lower', cmap = 'Greys_r', norm = ImageNormalize(stretch=LogStretch())) 
    plt.gca().add_patch(Ellipse((results['center']['x'] - ranges[0][0],results['center']['y'] - ranges[1][0]), 2*circ_ellipse_radii[-1], 2*circ_ellipse_radii[-1]*(1. - ellip),
                                phase*180/np.pi, fill = False, linewidth = 1, color = autocolours['blue1']))
    plt.plot([results['center']['x'] - ranges[0][0]],[results['center']['y'] - ranges[1][0]], marker = 'x', markersize = 3, color = autocolours['red1'])
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'initialize_ellipse_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi' in options else 300)
    plt.close()
    
def Plot_Isophote_Init_Optimize(circ_ellipse_radii, allphase, phase, pa_err, test_ellip, test_f2, ellip, ellip_err, results, options):
    fig, ax = plt.subplots(2,1, figsize = (6,6))
    plt.subplots_adjust(hspace = 0.01, wspace = 0.01)
    ax[0].plot(circ_ellipse_radii[:-1], ((-np.angle(allphase)/2) % np.pi)*180/np.pi, color = 'k')
    ax[0].axhline(phase*180/np.pi, color = 'r')
    ax[0].axhline((phase+pa_err)*180/np.pi, color = 'r', linestyle = '--')
    ax[0].axhline((phase-pa_err)*180/np.pi, color = 'r', linestyle = '--')
    #ax[0].axvline(circ_ellipse_radii[-2], color = 'orange', linestyle = '--')
    ax[0].set_xlabel('Radius [pix]', fontsize = 16)
    ax[0].set_ylabel('FFT$_{1}$ phase [deg]', fontsize = 16)
    ax[0].tick_params(labelsize = 12)
    ax[1].plot(test_ellip, test_f2, color = 'k')
    ax[1].axvline(ellip, color = 'r')
    ax[1].axvline(ellip + ellip_err, color = 'r', linestyle = '--')
    ax[1].axvline(ellip - ellip_err, color = 'r', linestyle = '--')
    ax[1].set_xlabel('Ellipticity [1 - b/a]', fontsize = 16)
    ax[1].set_ylabel('Loss [FFT$_{2}$/med(flux)]', fontsize = 16)
    ax[1].tick_params(labelsize = 14)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'initialize_ellipse_optimize_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi' in options else 300)
    plt.close()


# def Plot_Isophote_Fit(dat, sample_radii, ellip, pa, ellip_err, pa_err, results, options):

#     ranges = [[max(0,int(results['center']['x']-sample_radii[-1]*1.2)), min(dat.shape[1],int(results['center']['x']+sample_radii[-1]*1.2))],
#               [max(0,int(results['center']['y']-sample_radii[-1]*1.2)), min(dat.shape[0],int(results['center']['y']+sample_radii[-1]*1.2))]]
#     LSBImage(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]], results['background noise'])
#     # plt.imshow(np.clip(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]],
#     #                    a_min = 0,a_max = None), origin = 'lower', cmap = 'Greys', norm = ImageNormalize(stretch=LogStretch())) 
#     for i in range(len(sample_radii)):
#         plt.gca().add_patch(Ellipse((results['center']['x'] - ranges[0][0],results['center']['y'] - ranges[1][0]), 2*sample_radii[i], 2*sample_radii[i]*(1. - ellip[i]),
#                                     pa[i]*180/np.pi, fill = False, linewidth = ((i+1)/len(sample_radii))**2, color = autocolours['red1']))
#     if not ('ap_nologo' in options and options['ap_nologo']):
#         AddLogo(plt.gcf())
#     plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'fit_ellipse_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
#     plt.close()
        
#     plt.errorbar(np.array(sample_radii) * options['ap_pixscale'], ellip, yerr = ellip_err, color = autocolours['red1'], label = 'ellip [1-b/a]')
#     plt.errorbar(np.array(sample_radii) * options['ap_pixscale'], pa/np.pi, yerr = pa_err/np.pi, color = autocolours['blue1'], label = 'pa/$\\pi$')
#     plt.ylim([-0.01, 1.02])
#     plt.xlabel('Semi-major axis [arcsec]')
#     plt.ylabel('Elliptical Parameter Profile')
#     plt.legend()
#     plt.tight_layout()
#     if not ('ap_nologo' in options and options['ap_nologo']):
#         AddLogo(plt.gcf())
#     plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'phaseprofile_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
#     plt.close()

def Plot_Isophote_Fit(dat, sample_radii, parameters, results, options):
    for i in range(len(parameters)):
        if not 'm' in parameters[i]:
            parameters[i]['m'] = None
    Rlim = sample_radii[-1] * (1. if parameters[-1]['m'] is None else np.exp(sum(np.abs(parameters[-1]['Am'][m]) for m in range(len(parameters[-1]['m'])))))    
    ranges = [[max(0,int(results['center']['x']-Rlim*1.2)), min(dat.shape[1],int(results['center']['x']+Rlim*1.2))],
              [max(0,int(results['center']['y']-Rlim*1.2)), min(dat.shape[0],int(results['center']['y']+Rlim*1.2))]]
    LSBImage(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]], results['background noise'])
    for i in range(len(sample_radii)):
        N = max(15,int(0.9*2*np.pi*sample_radii[i]))
        theta = np.linspace(0, 2*np.pi*(1. - 1./N), N)
        R = sample_radii[i]*(np.ones(N) if parameters[i]['m'] is None else np.exp(sum(parameters[i]['Am'][m]*np.cos(parameters[i]['m'][m]*(theta + parameters[i]['Phim'][m])) for m in range(len(parameters[i]['m'])))))
        X = R*np.cos(theta)
        Y = R*(1-parameters[i]['ellip'])*np.sin(theta)
        X,Y = (X*np.cos(parameters[i]['pa']) - Y*np.sin(parameters[i]['pa']), X*np.sin(parameters[i]['pa']) + Y*np.cos(parameters[i]['pa']))
        X += results['center']['x'] - ranges[0][0]
        Y += results['center']['y'] - ranges[1][0]
        plt.plot(list(X) + [X[0]], list(Y) + [Y[0]], linewidth = ((i+1)/len(sample_radii))**2, color = autocolours['red1'])
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'fit_ellipse_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()
        
def _Plot_Isophotes(dat, R, parameters, results, options):
    for i in range(len(parameters)):
        if not 'm' in parameters[i]:
            parameters[i]['m'] = None
    Rlim = R[-1] * (1. if parameters[-1]['m'] is None else np.exp(sum(np.abs(parameters[-1]['Am'][m]) for m in range(len(parameters[-1]['m'])))))    
    ranges = [[max(0,int(results['center']['x']-Rlim*1.2)), min(dat.shape[1],int(results['center']['x']+Rlim*1.2))],
              [max(0,int(results['center']['y']-Rlim*1.2)), min(dat.shape[0],int(results['center']['y']+Rlim*1.2))]]
    LSBImage(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]], results['background noise'])
    fitlim = results['fit R'][-1] if 'fit R' in results else np.inf
    for i in range(len(R)):
        N = max(15,int(0.9*2*np.pi*R[i]))
        theta = np.linspace(0, 2*np.pi*(1. - 1./N), N)
        RR = R[i]*(np.ones(N) if parameters[i]['m'] is None else np.exp(sum(parameters[i]['Am'][m]*np.cos(parameters[i]['m'][m]*(theta + parameters[i]['Phim'][m])) for m in range(len(parameters[i]['m'])))))
        X = RR*np.cos(theta)
        Y = RR*(1-parameters[i]['ellip'])*np.sin(theta)
        X,Y = (X*np.cos(parameters[i]['pa']) - Y*np.sin(parameters[i]['pa']), X*np.sin(parameters[i]['pa']) + Y*np.cos(parameters[i]['pa']))
        X += results['center']['x'] - ranges[0][0]
        Y += results['center']['y'] - ranges[1][0]
        plt.plot(list(X) + [X[0]], list(Y) + [Y[0]], linewidth = ((i+1)/len(R))**2, color = autocolours['blue1'] if (i % 4 == 0) else autocolours['red1'], linestyle = '-' if R[i] < fitlim else '--')
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'photometry_ellipse_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()
    
    
def Plot_SB_Profile(dat, R, SB, SB_e, parameters, results, options):

    zeropoint = options['ap_zeropoint'] if 'ap_zeropoint' in options else 22.5
    
    CHOOSE = np.logical_and(SB < 99, SB_e < 1)
    if np.sum(CHOOSE) < 5:
        CHOOSE = np.ones(len(CHOOSE), dtype = bool)
    errscale = 1.
    if np.all(SB_e[CHOOSE] < 0.5):
        errscale = 1/np.max(SB_e[CHOOSE])
    lnlist = []
    lnlist.append(plt.errorbar(R[CHOOSE], SB[CHOOSE], yerr = errscale*SB_e[CHOOSE],
                               elinewidth = 1, linewidth = 0, marker = '.', markersize = 5, color = autocolours['red1'], label = 'Surface Brightness (err$\\cdot$%.1f)' % errscale))
    plt.errorbar(R[np.logical_and(CHOOSE,np.arange(len(CHOOSE)) % 4 == 0)],
                 SB[np.logical_and(CHOOSE,np.arange(len(CHOOSE)) % 4 == 0)],
                 yerr = SB_e[np.logical_and(CHOOSE,np.arange(len(CHOOSE)) % 4 == 0)],
                 elinewidth = 1, linewidth = 0, marker = '.', markersize = 5, color = autocolours['blue1'])
    plt.xlabel('Semi-Major-Axis [arcsec]', fontsize = 16)
    plt.ylabel('Surface Brightness [mag arcsec$^{-2}$]', fontsize = 16)
    plt.xlim([0,None])
    bkgrdnoise = -2.5*np.log10(results['background noise']) + zeropoint + 2.5*np.log10(options['ap_pixscale']**2)
    lnlist.append(plt.axhline(bkgrdnoise, color = 'purple', linewidth = 0.5, linestyle = '--', label = '1$\\sigma$ noise/pixel: %.1f mag arcsec$^{-2}$' % bkgrdnoise))
    plt.gca().invert_yaxis()
    plt.tick_params(labelsize = 14)
    labs = [l.get_label() for l in lnlist]
    plt.legend(lnlist, labs, fontsize = 11)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'photometry_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()                

    _Plot_Isophotes(dat, R[CHOOSE]/options['ap_pixscale'], list(compress(parameters, CHOOSE)), results, options)


def Plot_I_Profile(dat, R, I, I_e, parameters, results, options):

    CHOOSE = np.isfinite(I)
    if np.sum(CHOOSE) < 5:
        CHOOSE = np.ones(len(CHOOSE), dtype = bool)
    errscale = 1.
    lnlist = []
    lnlist.append(plt.errorbar(R[CHOOSE], I[CHOOSE], yerr = errscale*I_e[CHOOSE],
                               elinewidth = 1, linewidth = 0, marker = '.', markersize = 5, color = autocolours['red1'], label = 'Intensity (err$\\cdot$%.1f)' % errscale))
    plt.errorbar(R[np.logical_and(CHOOSE,np.arange(len(CHOOSE)) % 4 == 0)],
                 I[np.logical_and(CHOOSE,np.arange(len(CHOOSE)) % 4 == 0)],
                 yerr = I_e[np.logical_and(CHOOSE,np.arange(len(CHOOSE)) % 4 == 0)],
                 elinewidth = 1, linewidth = 0, marker = '.', markersize = 5, color = autocolours['blue1'])
    plt.xlabel('Semi-Major-Axis [arcsec]', fontsize = 16)
    plt.ylabel('Intensity [flux arcsec$^{-2}$]', fontsize = 16)
    plt.yscale('log')
    plt.xlim([0,None])
    bkgrdnoise = results['background noise'] / (options['ap_pixscale']**2)
    lnlist.append(plt.axhline(bkgrdnoise, color = 'purple', linewidth = 0.5, linestyle = '--', label = '1$\\sigma$ noise/pixel: %.1f flux arcsec$^{-2}$' % bkgrdnoise))
    plt.tick_params(labelsize = 14)
    labs = [l.get_label() for l in lnlist]
    plt.legend(lnlist, labs, fontsize = 11)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'photometry_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()                

    _Plot_Isophotes(dat, R[CHOOSE]/options['ap_pixscale'], list(compress(parameters, CHOOSE)), results, options)

def Plot_Phase_Profile(R, parameters, results, options):
    for i in range(len(parameters)):
        if not 'm' in parameters[i]:
            parameters[i]['m'] = None

    fig = plt.figure()
    if not parameters[0]['m'] is None:
        fig.add_subplot(2,1,1)
    else:
        fig.add_subplot(1,1,1)
    plt.plot(R, list(p['ellip'] for p in parameters), label = 'e [1 - b/a]', color = autocolours['red1'])
    plt.plot(R, list(p['pa']/np.pi for p in parameters), label = 'PA [rad/$\\pi$]', color = autocolours['blue1'])
    plt.legend(fontsize = 11)
    plt.xlabel('Semi-Major-Axis [arcsec]', fontsize = 16)
    #plt.ylabel('Ellipticity and Position Angle')
    plt.tick_params(labelsize = 14)
    if not parameters[0]['m'] is None:
        plt.xlabel('')
        fig.add_subplot(2,1,2)
        plt.subplots_adjust(hspace = 0)
        for m in range(len(parameters[0]['m'])):
            plt.plot(R, list(p['Am'][m] for p in parameters), label = 'A$_%i$' % parameters[0]['m'][m])
            plt.plot(R, list(p['Phim'][m]/(np.pi*parameters[0]['m'][m]) for p in parameters), label = '$\\phi_%i$ [rad/%i$\\pi$]' % (parameters[0]['m'][m],parameters[0]['m'][m]))
        plt.legend()
        plt.xlabel('Semi-Major-Axis [arcsec]', fontsize = 16)
        #plt.ylabel('Fourier Mode Parameters')
        plt.tick_params(labelsize = 14)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'phase_profile_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()                

def Plot_Meas_Fmodes(R, parameters, results, options):
    for i in range(len(parameters)):
        if not 'm' in parameters[i]:
            parameters[i]['m'] = None

    fig = plt.figure()
    if not parameters[0]['m'] is None:
        fig.add_subplot(2,1,1)
    else:
        fig.add_subplot(1,1,1)
    plt.plot(R, list(p['ellip'] for p in parameters), label = 'e [1 - b/a]', color = autocolours['red1'])
    plt.plot(R, list(p['pa']/np.pi for p in parameters), label = 'PA [rad/$\\pi$]', color = autocolours['blue1'])
    plt.legend(fontsize = 11)
    plt.xlabel('Semi-Major-Axis [arcsec]', fontsize = 16)
    #plt.ylabel('Ellipticity and Position Angle')
    plt.tick_params(labelsize = 14)
    if not parameters[0]['m'] is None:
        plt.xlabel('')
        fig.add_subplot(2,1,2)
        plt.subplots_adjust(hspace = 0)
        for m in range(len(parameters[0]['m'])):
            plt.plot(R, list(p['Am'][m] for p in parameters), label = 'A$_%i$' % parameters[0]['m'][m])
            plt.plot(R, list(p['Phim'][m]/np.pi for p in parameters), label = '$\\phi_%i$ [rad/$\\pi$]' % parameters[0]['m'][m])
        plt.legend()
        plt.xlabel('Semi-Major-Axis [arcsec]', fontsize = 16)
        #plt.ylabel('Fourier Mode Parameters')
        plt.tick_params(labelsize = 14)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'phase_profile_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()                

            

def Plot_Radial_Profiles(dat, sb, sbE, pa, nwedges, wedgeangles, wedgewidth, results, options):
    
    R = np.array(results['prof data']['R'])/options['ap_pixscale']
    SBE = np.array(results['prof data']['SB_e'])
    zeropoint = options['ap_zeropoint'] if 'ap_zeropoint' in options else 22.5
    CHOOSE = SBE < 0.2
    firstbad = np.argmax(np.logical_not(CHOOSE))
    if firstbad > 3:
        CHOOSE[firstbad:] = False
    ranges = [[max(0,int(results['center']['x']-1.5*R[CHOOSE][-1]-2)), min(dat.shape[1],int(results['center']['x']+1.5*R[CHOOSE][-1]+2))],
              [max(0,int(results['center']['y']-1.5*R[CHOOSE][-1]-2)), min(dat.shape[0],int(results['center']['y']+1.5*R[CHOOSE][-1]+2))]]
    # cmap = matplotlib.cm.get_cmap('tab10' if nwedges <= 10 else 'viridis')
    # colorind = np.arange(nwedges)/10
    cmap = cm.get_cmap('hsv')
    colorind = (np.linspace(0,1 - 1/nwedges,nwedges) + 0.1) % 1.
    for sa_i in range(len(wedgeangles)):
        CHOOSE = np.logical_and(np.array(sb[sa_i]) < 99, np.array(sbE[sa_i]) < 1)
        plt.errorbar(np.array(R)[CHOOSE]*options['ap_pixscale'], np.array(sb[sa_i])[CHOOSE], yerr = np.array(sbE[sa_i])[CHOOSE],
                     elinewidth = 1, linewidth = 0, marker = '.', markersize = 5, color = cmap(colorind[sa_i]), label = 'Wedge %.2f' % (wedgeangles[sa_i]*180/np.pi))
    plt.xlabel('Radius [arcsec]', fontsize = 16)
    plt.ylabel('Surface Brightness [mag arcsec$^{-2}$]', fontsize = 16)
    bkgrdnoise = -2.5*np.log10(results['background noise']) + zeropoint + 2.5*np.log10(options['ap_pixscale']**2)
    plt.axhline(bkgrdnoise, color = 'purple', linewidth = 0.5, linestyle = '--', label = '1$\\sigma$ noise/pixel:\n%.1f mag arcsec$^{-2}$' % bkgrdnoise)
    plt.gca().invert_yaxis()
    plt.legend(fontsize = 15)
    plt.tick_params(labelsize = 14)
    plt.tight_layout()
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'radial_profiles_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()
    
    LSBImage(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]], results['background noise'])
    
    cx, cy = (results['center']['x'] - ranges[0][0], results['center']['y'] - ranges[1][0])
    for sa_i in range(len(wedgeangles)):
        if np.all(pa == pa[0]):
            plt.gca().add_patch(Wedge((cx,cy), R[-1], (wedgeangles[sa_i]+pa[0] - wedgewidth[-1]/2)*180/np.pi, (wedgeangles[sa_i]+pa[0] + wedgewidth[-1]/2)*180/np.pi, facecolor = cmap(colorind[sa_i]), linewidth = 0, alpha = 0.3)) 
        else:
            endx, endy = (R*np.cos(wedgeangles[sa_i]+pa), R*np.sin(wedgeangles[sa_i]+pa))
            plt.plot(endx + cx, endy + cy, color = 'w', linewidth = 1.1)
            plt.plot(endx + cx, endy + cy, color = cmap(colorind[sa_i]), linewidth = 0.7)
            endx, endy = (R*np.cos(wedgeangles[sa_i]+pa + wedgewidth/2), R*np.sin(wedgeangles[sa_i]+pa + wedgewidth/2))
            plt.plot(endx + cx, endy + cy, color = 'w', linewidth = 0.7)
            plt.plot(endx + cx, endy + cy, color = cmap(colorind[sa_i]), linestyle = '--', linewidth = 0.5)
            endx, endy = (R*np.cos(wedgeangles[sa_i]+pa - wedgewidth/2), R*np.sin(wedgeangles[sa_i]+pa - wedgewidth/2))
            plt.plot(endx + cx, endy + cy, color = 'w', linewidth = 0.7)
            plt.plot(endx + cx, endy + cy, color = cmap(colorind[sa_i]), linestyle = '--', linewidth = 0.5)
            
    plt.xlim([0,ranges[0][1] - ranges[0][0]])
    plt.ylim([0,ranges[1][1] - ranges[1][0]])
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'radial_profiles_wedges_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()


def Plot_Axial_Profiles(dat, R, sb, sbE, pa, results, options):

    zeropoint = options['ap_zeropoint'] if 'ap_zeropoint' in options else 22.5
    count = 0
    for rd in [1,-1]:
        for ang in [1, -1]:
            key = (rd,ang)
            #cmap = matplotlib.cm.get_cmap('viridis_r')
            norm = matplotlib.colors.Normalize(vmin=0, vmax=R[-1]*options['ap_pixscale'])
            for pi, pR in enumerate(R):
                if pi % 3 != 0:
                    continue
                CHOOSE = np.logical_and(np.array(sb[key][pi]) < 99, np.array(sbE[key][pi]) < 1)
                plt.errorbar(np.array(R)[CHOOSE]*options['ap_pixscale'], np.array(sb[key][pi])[CHOOSE], yerr = np.array(sbE[key][pi])[CHOOSE],
                             elinewidth = 1, linewidth = 0, marker = '.', markersize = 3, color = autocmap.reversed()(norm(pR*options['ap_pixscale'])))
            plt.xlabel('%s-axis position on line [arcsec]' % ('Major' if 'ap_axialprof_parallel' in options and options['ap_axialprof_parallel'] else 'Minor'), fontsize = 16)
            plt.ylabel('Surface Brightness [mag arcsec$^{-2}$]', fontsize = 16)
            # cb1 = matplotlib.colorbar.ColorbarBase(plt.gca(), cmap=cmap,
            #                                        norm=norm)
            cb1 = plt.colorbar(matplotlib.cm.ScalarMappable(norm = norm, cmap = autocmap.reversed()))
            cb1.set_label('%s-axis position of line [arcsec]'  % ('Minor' if 'ap_axialprof_parallel' in options and options['ap_axialprof_parallel'] else 'Major'), fontsize = 16)
            # plt.colorbar()
            bkgrdnoise = -2.5*np.log10(results['background noise']) + zeropoint + 2.5*np.log10(options['ap_pixscale']**2)
            plt.axhline(bkgrdnoise, color = 'purple', linewidth = 0.5, linestyle = '--', label = '1$\\sigma$ noise/pixel: %.1f mag arcsec$^{-2}$' % bkgrdnoise)
            plt.gca().invert_yaxis()
            plt.legend(fontsize = 15)
            plt.tick_params(labelsize = 14)
            plt.title('%sR : pa%s90' % ('+' if rd > 0 else '-', '+' if ang > 0 else '-'), fontsize = 15)
            plt.tight_layout()
            if not ('ap_nologo' in options and options['ap_nologo']):
                AddLogo(plt.gcf())
            plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'axial_profile_q%i_%s.jpg' % (count, options['ap_name'])), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
            plt.close()
            count += 1


    CHOOSE = np.array(results['prof data']['SB_e']) < 0.2
    firstbad = np.argmax(np.logical_not(CHOOSE))
    if firstbad > 3:
        CHOOSE[firstbad:] = False
    outto = np.array(results['prof data']['R'])[CHOOSE][-1]*1.5/options['ap_pixscale']
    ranges = [[max(0,int(results['center']['x']-outto-2)), min(dat.shape[1],int(results['center']['x']+outto+2))],
              [max(0,int(results['center']['y']-outto-2)), min(dat.shape[0],int(results['center']['y']+outto+2))]]
    LSBImage(dat[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]], results['background noise'])
    count = 0
    cmap = matplotlib.cm.get_cmap('hsv')
    colorind = (np.linspace(0,1 - 1/4,4) + 0.1) % 1
    colours = list(cmap(c) for c in colorind) #['b', 'r', 'orange', 'limegreen']
    for rd in [1,-1]:
        for ang in [1, -1]:
            key = (rd,ang)
            branch_pa = (pa + ang*np.pi/2) % (2*np.pi)
            for pi, pR in enumerate(R):
                if pi % 3 != 0:
                    continue
                start = np.array([results['center']['x'] + ang*rd*pR*np.cos(pa + (0 if ang > 0 else np.pi)),
                                  results['center']['y'] + ang*rd*pR*np.sin(pa + (0 if ang > 0 else np.pi))])
                end = start + R[-1]*np.array([np.cos(branch_pa), np.sin(branch_pa)])
                start -= np.array([ranges[0][0], ranges[1][0]])
                end -= np.array([ranges[0][0], ranges[1][0]])
                plt.plot([start[0],end[0]], [start[1],end[1]], linewidth = 0.5, color = colours[count], label = ('%sR : pa%s90' % ('+' if rd > 0 else '-', '+' if ang > 0 else '-')) if pi == 0 else None)
            count += 1
    plt.legend()
    plt.xlim([0,ranges[0][1] - ranges[0][0]])
    plt.ylim([0,ranges[1][1] - ranges[1][0]])
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'axial_profile_lines_%s.jpg' % options['ap_name']), dpi = options['ap_plotdpi'] if 'ap_plotdpi' in options else 300)
    plt.close()        
    

def Plot_EllipseModel(IMG, Model, R, modeltype, results, options):

    ranges = [[max(0,int(results['center']['x']-R[-1]*1.2)), min(IMG.shape[1],int(results['center']['x']+R[-1]*1.2))],
              [max(0,int(results['center']['y']-R[-1]*1.2)), min(IMG.shape[0],int(results['center']['y']+R[-1]*1.2))]]
    plt.figure(figsize = (7,7))
    autocmap.set_under('k', alpha=0)
    showmodel = Model[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]].copy()
    showmodel[showmodel > 0] += np.max(showmodel)/(10**3.5) - np.min(showmodel[showmodel > 0])
    plt.imshow(showmodel, origin = 'lower', cmap = autocmap, norm = ImageNormalize(stretch=LogStretch(), clip = False))
    plt.axis('off')
    plt.subplots_adjust(left=0.03, right=0.97, top=0.97, bottom=0.05)
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'ellipsemodel_%s_%s.jpg' % (modeltype,options['ap_name'])), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()
        
    residual = IMG[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]] - results['background'] - Model[ranges[1][0]: ranges[1][1], ranges[0][0]: ranges[0][1]]
    plt.figure(figsize = (7,7))
    plt.imshow(residual, origin = 'lower', cmap = 'PuBu',
               vmin = np.quantile(residual, 0.0001), vmax = 0)
    plt.imshow(np.clip(residual,a_min = 0, a_max = np.quantile(residual,0.9999)),
               origin = 'lower', cmap = autocmap, norm = ImageNormalize(stretch=LogStretch(), clip = False),
               interpolation = 'none', clim = [1e-5, None])        
    plt.axis('off')
    plt.subplots_adjust(left=0.03, right=0.97, top=0.97, bottom=0.05)
    if not ('ap_nologo' in options and options['ap_nologo']):
        AddLogo(plt.gcf())
    plt.savefig(os.path.join(options['ap_plotpath'] if 'ap_plotpath' in options else '', 'ellipseresidual_%s_%s.jpg' % (modeltype,options['ap_name'])), dpi = options['ap_plotdpi'] if 'ap_plotdpi'in options else 300)
    plt.close()
    
