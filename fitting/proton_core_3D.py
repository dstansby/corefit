# Script to read and process 3D Helios ion distribution functions.
#
# David Stansby 2017
from datetime import timedelta

import pandas as pd
import numpy as np
import scipy.optimize as opt

import heliopy.data.helios as HeliosImport
import heliopy.constants as const
import heliopy.plasma as helioplas

from helpers import rotationmatrix


# Dictionary mapping status codes to messages explaining the codes
statusdict = {1: 'Fitting successful',
              2: 'No magnetic field data available',
              3: 'Magnetic field varies too much for a reliable fit',
              4: 'Fitted bulk velocity outside distribution velocity bounds',
              5: 'Less than 6 points available for fitting',
              6: 'Least square fitting failed',
              9: 'Think there is more than one distribution in file',
              10: 'Proton peak not present in 3D distribution',
              11: 'Number density physically unrealistic',
              12: 'Less than 3 angular bins available in either direction',
              13: 'Temperature physically unrealistic'}


def return_nans(status, time, instrument):
    '''Return np.nan for all parameters apart from "Time" and "status"'''
    assert type(status) == int, 'Status code must be an integer'
    fitparams = {'n_p': np.nan,
                 'vth_p_perp': np.nan,
                 'vth_p_par': np.nan,
                 'Tp_perp': np.nan,
                 'Tp_par': np.nan,
                 'vp_x': np.nan,
                 'vp_y': np.nan,
                 'vp_z': np.nan,

                 'Time': time,
                 'Status': status,
                 'Instrument': instrument,

                 'B instrument': np.nan,
                 'Bx': np.nan,
                 'By': np.nan,
                 'Bz': np.nan,
                 'sigma B': np.nan}
    return fitparams


def bi_maxwellian_3D(vx, vy, vz, A, vth_perp, vth_z, vbx, vby, vbz):
    '''
    Return distribution function at (vx, vy, vz),
    given 6 distribution parameters.
    '''
    # Put in bulk frame
    vx = vx - vbx
    vy = vy - vby
    vz = vz - vbz
    exponent = (vx / vth_perp)**2 + (vy / vth_perp)**2 + (vz / vth_z)**2
    return A * np.exp(-exponent)


def iondistfitting(dist, params, fit_1D, mag4hz, mag6s, starttime, I1a, I1b,
                   plotfigs=False):
    '''
    Method to do 3D fitting to an individual ion distribution
    '''
    output = {}
    instrument = int(params['ion_instrument'])
    output['Instrument'] = instrument
    # Return if the 1D fit thinks there are two distributions functions in
    # one file
    if fit_1D['status'] == 9:
        return return_nans(9, starttime, instrument)

    if (dist['counts'] < 0).any():
        return return_nans(9, starttime, instrument)
    # Get rid of energies higher than energies in the I1a 1D distribution
    dist = dist[dist['|v|'] <= I1a['v'].max() * 1e3]

    # Return if not enought points to do fitting
    if dist.shape[0] <= 6:
        return return_nans(5, starttime, instrument)

    phi_bins = len(dist.index.get_level_values('Az').unique())
    theta_bins = len(dist.index.get_level_values('El').unique())
    if phi_bins < 3 or theta_bins < 3:
        return return_nans(12, starttime, instrument)

    # Return if the minimum velocity in the I1a/I3 distribution is not below
    # the peak in I1b (assumed to be the proton peak)
    vs_3D = dist['|v|'] / 1e3
    if len(I1a) != 0:
        if vs_3D.min() > I1a['df'].argmax():
            return return_nans(10, starttime, instrument)

    # Estimate the times during which the distribution was measured
    E_bins = dist.index.get_level_values('E_bin').values
    dist_starttime = starttime + timedelta(seconds=int(np.min(E_bins)))
    dist_endtime = starttime + timedelta(seconds=int(np.max(E_bins)) + 1)
    print('Distribution measured between', dist_starttime, '-->', dist_endtime)

    # Distribution function in s**3 / cm**6
    df = dist['pdf'].values
    # Spacecraft frame velocities in km/s
    vs = dist[['vx', 'vy', 'vz']].values / 1e3

    if mag4hz is None:
        magempty = True
    else:
        # Get magnetic field whilst distribution was built up
        mag = mag4hz[np.logical_and(mag4hz.index > dist_starttime,
                                    mag4hz.index < dist_endtime)]
        magempty = mag.empty

    # If no 4Hz data, and 6s data available
    if magempty and (mag6s is not None):
        mag = mag6s[np.logical_and(mag6s.index.values > dist_starttime,
                                   mag6s.index.values < dist_endtime)]
        magempty = mag.empty
        # No 4Hz or 6s data
        if magempty:
            output['B instrument'] = np.nan
        # No 4hz, but 6s available
        else:
            output['B instrument'] = 2
    # 4Hz data available
    else:
        output['B instrument'] = 1

    if not magempty:
        # Check magnetic field is static enough
        mag = mag[['Bx', 'By', 'Bz']].values
        # Use average magnetic field
        B = np.mean(mag, axis=0)
        sigmaB = np.std(mag, axis=0)
        sigmaB = np.linalg.norm(sigmaB)
        output['Bx'] = B[0]
        output['By'] = B[1]
        output['Bz'] = B[2]
        output['sigma B'] = sigmaB
        # Rotation matrix that rotates into field aligned frame where B = zhat
        R = rotationmatrix(B)
        # Rotate velocities into field aligned co-ordinates
        vprime = np.dot(R, vs.T).T
    else:
        output['Bx'] = np.nan
        output['By'] = np.nan
        output['Bz'] = np.nan
        output['sigma B'] = np.nan
        # If no magnetic field, still get a number density and velocities
        vprime = vs

    # Initial proton parameter guesses
    # Take maximum of distribution function for amplitude
    Ap_guess = np.max(df)
    # Take average ion velocity for v_p
    vp_guess = [np.sum(df * vprime[:, 0]) / np.sum(df),
                np.sum(df * vprime[:, 1]) / np.sum(df),
                np.sum(df * vprime[:, 2]) / np.sum(df)]
    # Take proton temperature in distribution parameters for T_p (par and perp)
    # If no guess, or guess < 10km/s or guess > 60km/s take 50km/s for guess
    vthp_guess = helioplas.temp2vth(fit_1D['T_p'], const.m_p)
    if (not np.isfinite(vthp_guess)) or vthp_guess < 10 or vthp_guess > 100:
        vthp_guess = 40
    guesses = (Ap_guess, vthp_guess, vthp_guess,
               vp_guess[0], vp_guess[1], vp_guess[2])

    # Residuals to minimize
    def resid(args, vprime, df):
        fit = bi_maxwellian_3D(vprime[:, 0], vprime[:, 1],
                               vprime[:, 2], *args[:6])
        return df - fit

    fitout = opt.leastsq(resid, guesses, args=(vprime, df),
                         full_output=True)

    fitmsg = fitout[3]
    fitstatus = fitout[4]
    fitparams = fitout[0]

    # Check on fit result status. Return if not successfull
    if fitstatus not in (1, 2, 3, 4):
        return return_nans(6, starttime, instrument)

    # Return if number density is physically unreasonable
    # (> or < 10 times the peak in the distribution function)
    if (((fitparams[0] > 20 * np.max(df)) or
         (fitparams[0] < 0.1 * np.max(df))) and
            not magempty):
        return return_nans(11, starttime, instrument)

    if (((fitparams[1] < 5) or
         (fitparams[2] < 5)) and
            not magempty):
        return return_nans(12, starttime, instrument)

    def process_fitparams(fitparams, species):
        v = fitparams[3:6]

        # If no magnetic field data, set temperatures to nans
        if magempty:
            fitparams[1:3] = np.nan
        else:
            # Otherwise transformt bulk velocity back into spacecraft frame
            v = np.dot(R.T, v)

        # Check that fitted bulk velocity is within the velocity range of
        # the distribution function, and return if any one component is outside
        for i in range(0, 3):
            if v[i] < np.min(vs[:, i]) or v[i] > np.max(vs[:, i]):
                return 4
            elif np.linalg.norm(v) < np.min(np.linalg.norm(vs, axis=1)):
                return 4

        fit_dict = {'vth_' + species + '_perp': np.abs(fitparams[1]),
                    'vth_' + species + '_par': np.abs(fitparams[2])}
        m = const.m_p
        fit_dict['T' + species + '_perp'] =\
            helioplas.vth2temp(fit_dict['vth_' + species + '_perp'], m)
        fit_dict['T' + species + '_par'] =\
            helioplas.vth2temp(fit_dict['vth_' + species + '_par'], m)
        # Original distribution has units s**3 / m**6
        # Get n_p in 1 / m**3
        n = (fitparams[0] * np.power(np.pi, 1.5) *
             np.abs(fitparams[1]) * 1e3 *
             np.abs(fitparams[1]) * 1e3 *
             np.abs(fitparams[2]) * 1e3)
        # Convert to 1 / cm**3
        n *= 1e-6
        fit_dict.update({'n_' + species: n})
        '''
        if n < 0:
            return return_nans(11, starttime, instrument)
        '''
        # Remove spacecraft abberation
        # Velocities here are all in km/s
        v_x = v[0] + params['helios_vr']
        v_y = v[1] + params['helios_v']
        v_z = v[2]
        fit_dict.update({'v' + species + '_x': v_x,
                         'v' + species + '_y': v_y,
                         'v' + species + '_z': v_z})

        return fit_dict

    fit_dict = process_fitparams(fitparams[:6], 'p')
    if isinstance(fit_dict, int):
        return return_nans(fit_dict, starttime, instrument)
    output.update(fit_dict)

    if magempty:
        status = 2
    else:
        status = 1
    output.update({'Time': starttime,
                   'Status': status,
                   'Instrument': instrument})

    #########################
    # Fitting finishes here #
    #########################
    if plotfigs:
        print(guesses)
        print(output)
        # from plot_fitted_dist import plot_dist
        # plot_dist(starttime, dist, params, pd.Series(output), I1a, I1b)

    return output