#! /usr/bin/env python

from optparse import OptionParser

if __name__ == '__main__':  # noqa F402
    import matplotlib
    matplotlib.use('Agg')

import imsimUtils

import pylab as plt
import numpy as np


def main():
    parser = OptionParser()
    imsimUtils.addOptions(parser)
    (opt, args) = parser.parse_args()

    inButler = imsimUtils.getInputButler(opt)
    allkeys = imsimUtils.getAllKeys(opt, inButler)

    solvedindex = []
    for keys in allkeys:
        pmatches = inButler.get('icMatch', **keys)
        matchmeta = pmatches.getSourceMatchMetadata()
        indexid = matchmeta.getInt('ANINDID')
        print('Solved with', indexid)
        solvedindex.append(indexid)

    solvedindex = np.array(solvedindex)
    U = np.unique(solvedindex)
    U.sort()
    Ntotal = len(solvedindex)
    for ind in U:
        N = sum(solvedindex == ind)
        print('Index', ind, 'solved', N, 'or %.1f %%' % (100. * N / float(Ntotal)))

    plt.clf()
    plt.hist(solvedindex)
    plt.xlabel('Astrometry.net index ID')
    plt.ylabel('Number of CCDs solved')
    plt.savefig('solvedindex.png')


if __name__ == '__main__':
    main()
