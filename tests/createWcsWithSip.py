#!/usr/bin/env python

# 
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import os
import unittest

import eups
import lsst.afw.table as afwTable
import lsst.utils.tests as utilsTests
import lsst.afw.geom as afwGeom

import lsst.meas.astrom as measAst
import lsst.meas.astrom.sip as sip
import lsst.meas.astrom.sip.genDistortedImage as distort
import lsst.meas.astrom.sip.cleanBadPoints as cleanBadPoints

############################
# Set up local astrometry_net_data
meas_astrom_dir = eups.productDir("meas_astrom")
datapath = os.path.join(meas_astrom_dir, 'tests', 'astrometry_net_data', 'cfhttemplate')
eupsObj = eups.Eups(root=datapath)
ok, version, reason = eupsObj.setup('astrometry_net_data')
if not ok:
    raise ValueError("Can't find astrometry_net_data version cfhttemplate (from path: %s): %s" %
                     (datapath, reason))

class CreateWcsWithSipCase(unittest.TestCase):
    def setUp(self):

        self.conf = measAst.MeasAstromConfig()
        self.astrom = measAst.Astrometry(self.conf) #, logLevel=pexLog.Log.DEBUG)

        path=eups.productDir("meas_astrom")
        self.filename=os.path.join(path, "tests", "cat.xy.fits")
        self.tolArcsec = .4 
        self.tolPixel = .1

    def tearDown(self):
        del self.conf
        del self.astrom

        import lsst.meas.astrom.astrometry_net as an
        an.finalize()

    def testBigXy0(self):
        # test for ticket #2710
        from lsst.pex.logging import Log
        log = Log.getDefaultLog()
        log.setThreshold(Log.DEBUG);
        self.astrom.log = log
        x0,y0 = 200000, 500000
        cx = 500
        a2 = 1e-5
        cat = afwTable.SourceCatalog.readFits(self.filename)
        print 'Catalog size', len(cat)
        # Source x,y positions are ~ (500,1500) x (500,1500)
        xKey = cat.table.getCentroidKey().getX()
        yKey = cat.table.getCentroidKey().getY()
        for src in cat:
            x = src.get(xKey) - 500
            dx = x - cx
            x += a2 * (dx**2)
            src.set(xKey, x + x0)
            src.set(yKey, src.get(yKey) - 500 + y0)
        res = self.astrom.determineWcs2(cat, imageSize=(1000,1000),
                                        x0=x0, y0=y0)
        print 'Got result', res
        print 'SIP:', res.sipWcs.getFitsMetadata().toString()

        wcs = res.wcs
        for src in cat:
            rd = wcs.pixelToSky(src.getCentroid())
            xy = wcs.skyToPixel(rd)
            #print 'src', src.getX(), src.getY()
            #print 'rd', rd
            #print 'xy', xy
            #print 'dx,dy', xy[0] - src.getX(), xy[1] - src.getY()
            self.assertTrue(abs(xy[0] - src.getX()) < 0.1)
            self.assertTrue(abs(xy[1] - src.getY()) < 0.1)
        
    def testLinearXDistort(self):
        print "linearXDistort"
        self.singleTestInstance(self.filename, distort.linearXDistort)

    def testLinearYDistort(self):
        print "linearYDistort"
        self.singleTestInstance(self.filename, distort.linearYDistort)

    def testQuadraticDistort(self):
        print "linearQuadraticDistort"
        self.singleTestInstance(self.filename, distort.linearYDistort)
    
    def singleTestInstance(self, filename, distortFunc):
        cat = self.loadCatalogue(self.filename)
        img = distort.distortList(cat, distortFunc)
        res = self.astrom.determineWcs2(img, imageSize=(1000,1000))
        imgWcs = res.getWcs()

        def printWcs(wcs):
            print "WCS metadata:"
            md = wcs.getFitsMetadata()
            for name in md.names():
                print "%s: %r" % (name, md.get(name))

        printWcs(imgWcs)

        #Create a wcs with sip
        cat = cat.cast(afwTable.SimpleCatalog, False)
        matchList = self.matchSrcAndCatalogue(cat, img, imgWcs)
        print "*** num matches =", len(matchList)
        return
        sipObject = sip.makeCreateWcsWithSip(matchList, imgWcs, 3)

        #print 'Put in TAN Wcs:'
        #print imgWcs.getFitsMetadata().toString()
        imgWcs = sipObject.getNewWcs()
        #print 'Got SIP Wcs:'
        #print imgWcs.getFitsMetadata().toString()

        # Write out the SIP header
        #afwImage.fits_write_imageF('createWcsWithSip.sip', afwImage.ImageF(0,0),
        #imgWcs.getFitsMetadata())

        print 'number of matches:', len(matchList), sipObject.getNPoints()
        scatter = sipObject.getScatterOnSky().asArcseconds()
        print "Scatter in arcsec is %g" % (scatter)

        self.assertTrue(scatter < self.tolArcsec, "Scatter exceeds tolerance in arcsec")

        if False:
            scatter = sipObject.getScatterInPixels()
            self.assertTrue(scatter < self.tolPixel, "Scatter exceeds tolerance in pixels: %g" %(scatter))
        

    def loadCatalogue(self, filename):
        """Load a list of xy points from a file, solve for position, and
        return a SourceSet of points"""

        cat = afwTable.SourceCatalog.readFits(filename)

        # Source x,y positions are ~ (500,1500) x (500,1500)
        xKey = cat.table.getCentroidKey().getX()
        yKey = cat.table.getCentroidKey().getY()
        for src in cat:
            src.set(xKey, src.get(xKey) - 500)
            src.set(yKey, src.get(yKey) - 500)
            
        res = self.astrom.determineWcs2(cat, imageSize=(1000,1000))
        catWcs = res.getWcs()

        #Set catalogue ra and decs
        for src in cat:
            src.updateCoord(catWcs)
        return cat

    def matchSrcAndCatalogue(self, cat, img, imgWcs, dist=1.*afwGeom.arcseconds, cleanParam=3):
        """Given an input catalogue, match a list of objects in an image, given
        their x,y position and a wcs solution.

        Return: A list of x, y, dx and dy. Each element of the list is itself a list
        """

        matcher = sip.MatchSrcToCatalogue(cat, img, imgWcs, dist)
        matchList = matcher.getMatches()

        mList = cleanBadPoints.clean(matchList, imgWcs, order=cleanParam)
        return mList

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""
    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(CreateWcsWithSipCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)

    return unittest.TestSuite(suites)

def run(exit=False):
    """Run the tests"""
    utilsTests.run(suite(), exit)



 
if __name__ == "__main__":
    run(True)
