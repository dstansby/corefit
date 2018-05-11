import yt
import numpy as np
import heliopy.data.helios as helios
import helpers


def get_isocontour(pdf, bbox, value):
    data = dict(density=(pdf, "g/cm**3"))
    ds = yt.load_uniform_grid(data, pdf.shape, length_unit="km", bbox=bbox)
    surface = ds.surface(ds.all_data(), "density", value)
    return surface


def plot_3D(probe, time):
    # Load distribution
    args = (probe, time.year, int(time.strftime('%j')),
            time.hour, time.minute, time.second)
    dist = helios.ion_dist_single(*args)
    vs = dist[['vx', 'vy', 'vz']].values / 1e3
    pdf = dist['pdf'].values
    for i in range(vs.shape[1]):
        vs[:, i] -= np.nanmean(vs[:, i])
    print(vs, pdf)

    vlim = 400
    x, y, z, pdf = helpers.interp_dist(vs, pdf, 40, vlim)
    pdf[~np.isfinite(pdf)] = 0
    bbox = np.array([[-vlim, vlim], [-vlim, vlim], [-vlim, vlim]])
    surface = get_isocontour(pdf, bbox, 1e-9)
    surface.export_obj('test')


if __name__ == '__main__':
    import argparse
    from datetime import datetime
    import matplotlib.pyplot as plt
    description = ('Plot in 3D a single Helios 3D ion distribution.')
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('probe', metavar='p', type=str, nargs=1,
                        help='Helios probe')
    parser.add_argument('date', metavar='d', type=str, nargs=1,
                        help='Date - must be formatted as YYYY/MM/DD')
    parser.add_argument('time', metavar='t', type=str, nargs=1,
                        help='Time - must be formatted as HH:MM:SS')

    args = parser.parse_args()
    date = datetime.strptime(args.date[0] + ' ' + args.time[0],
                             '%Y/%m/%d %H:%M:%S')
    plot_3D(args.probe[0], date)
