// -*- LSST-C++ -*-

/*
 * LSST Data Management System
 * Copyright 2016 LSST/AURA
 *
 * This product includes software developed by the
 * LSST Project (http://www.lsst.org/).
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the LSST License Statement and
 * the GNU General Public License along with this program.  If not,
 * see <http://www.lsstcorp.org/LegalNotices/>.
 */

#include <sstream>

#include "lsst/afw/coord/Coord.h"
#include "lsst/afw/image/TanWcs.h"
#include "lsst/meas/astrom/SipTransform.h"

namespace lsst { namespace meas { namespace astrom {

SipForwardTransform SipForwardTransform::convert(
    PolynomialTransform const & poly,
    afw::geom::Point2D const & pixelOrigin,
    afw::geom::LinearTransform const & cdMatrix
) {
    auto forwardSipPoly = compose(
        afw::geom::AffineTransform(cdMatrix.invert()),
        compose(
            poly,
            afw::geom::AffineTransform(afw::geom::Extent2D(pixelOrigin))
        )
    );
    // Subtracting 1 here accounts for the extra terms outside the sum in the
    // transform definition (see class docs) - note that you can fold those
    // terms into the sum by adding 1 from the A_10 and B_01 terms.
    forwardSipPoly._xCoeffs(1, 0) -= 1;
    forwardSipPoly._yCoeffs(0, 1) -= 1;
    return SipForwardTransform(pixelOrigin, cdMatrix, forwardSipPoly);
}

SipForwardTransform SipForwardTransform::convert(
    ScaledPolynomialTransform const & scaled,
    afw::geom::Point2D const & pixelOrigin,
    afw::geom::LinearTransform const & cdMatrix
) {
    auto forwardSipPoly = compose(
        afw::geom::AffineTransform(cdMatrix.invert())*scaled.getOutputScalingInverse(),
        compose(
            scaled.getPoly(),
            scaled.getInputScaling()*afw::geom::AffineTransform(afw::geom::Extent2D(pixelOrigin))
        )
    );
    // Account for the terms outside the sum in the definition (see comment
    // earlier in the file for more explanation).
    forwardSipPoly._xCoeffs(1, 0) -= 1;
    forwardSipPoly._yCoeffs(0, 1) -= 1;
    return SipForwardTransform(pixelOrigin, cdMatrix, forwardSipPoly);
}

SipForwardTransform SipForwardTransform::convert(ScaledPolynomialTransform const & scaled) {
    afw::geom::Point2D pixelOrigin(-scaled.getOutputScalingInverse().getTranslation());
    afw::geom::LinearTransform cdMatrix(scaled.getInputScaling().getLinear().invert());
    return convert(scaled, pixelOrigin, cdMatrix);
}

afw::geom::AffineTransform SipForwardTransform::linearize(afw::geom::Point2D const & in) const {
    afw::geom::AffineTransform tail(-afw::geom::Extent2D(getPixelOrigin()));
    return afw::geom::AffineTransform(_cdMatrix)
        * (afw::geom::AffineTransform() + _poly.linearize(tail(in)))
        * tail;
}

afw::geom::Point2D SipForwardTransform::operator()(afw::geom::Point2D const & uv) const {
    afw::geom::Point2D duv(uv - afw::geom::Extent2D(getPixelOrigin()));
    return getCDMatrix()(afw::geom::Extent2D(duv) + getPoly()(duv));
}

SipReverseTransform SipReverseTransform::convert(
    PolynomialTransform const & poly,
    afw::geom::Point2D const & pixelOrigin,
    afw::geom::LinearTransform const & cdMatrix
) {
    auto reverseSipPoly = compose(
        afw::geom::AffineTransform(-afw::geom::Extent2D(pixelOrigin)),
        compose(
            poly,
            afw::geom::AffineTransform(cdMatrix)
        )
    );
    // Account for the terms outside the sum in the definition (see comment
    // earlier in the file for more explanation).
    reverseSipPoly._xCoeffs(1, 0) -= 1;
    reverseSipPoly._yCoeffs(0, 1) -= 1;
    return SipReverseTransform(pixelOrigin, cdMatrix, reverseSipPoly);
}

SipReverseTransform SipReverseTransform::convert(
    ScaledPolynomialTransform const & scaled,
    afw::geom::Point2D const & pixelOrigin,
    afw::geom::LinearTransform const & cdMatrix
) {
    auto reverseSipPoly = compose(
        afw::geom::AffineTransform(-afw::geom::Extent2D(pixelOrigin))
        *scaled.getOutputScalingInverse(),
        compose(
            scaled.getPoly(),
            scaled.getInputScaling()*afw::geom::AffineTransform(cdMatrix)
        )
    );
    // Account for the terms outside the sum in the definition (see comment
    // earlier in the file for more explanation).
    reverseSipPoly._xCoeffs(1, 0) -= 1;
    reverseSipPoly._yCoeffs(0, 1) -= 1;
    return SipReverseTransform(pixelOrigin, cdMatrix, reverseSipPoly);
}

SipReverseTransform SipReverseTransform::convert(ScaledPolynomialTransform const & scaled) {
    return convert(
        scaled,
        afw::geom::Point2D(scaled.getOutputScalingInverse().getTranslation()),
        scaled.getInputScaling().getLinear()
    );
}

afw::geom::AffineTransform SipReverseTransform::linearize(afw::geom::Point2D const & in) const {
    return afw::geom::AffineTransform(afw::geom::Extent2D(getPixelOrigin()))
        * (afw::geom::AffineTransform() + _poly.linearize(_cdInverse(in)))
        * _cdInverse;
}

afw::geom::Point2D SipReverseTransform::operator()(afw::geom::Point2D const & xy) const {
    afw::geom::Point2D UV = _cdInverse(xy);
    return afw::geom::Extent2D(UV) + afw::geom::Extent2D(getPixelOrigin()) + getPoly()(UV);
}


PTR(afw::image::TanWcs) makeWcs(
    SipForwardTransform const & sipForward,
    SipReverseTransform const & sipReverse,
    afw::coord::Coord const & skyOrigin
) {
    if (!sipForward.getPixelOrigin().asEigen().isApprox(sipReverse.getPixelOrigin().asEigen())) {
        std::ostringstream oss;
        oss << "SIP forward and reverse transforms have inconsistent CRPIX: "
            << sipForward.getPixelOrigin() << " != " << sipReverse.getPixelOrigin();
        throw LSST_EXCEPT(
            pex::exceptions::InvalidParameterError,
            oss.str()
        );
    }
    if (!sipForward.getCDMatrix().getMatrix().isApprox(sipReverse.getCDMatrix().getMatrix())) {
        std::ostringstream oss;
        oss << "SIP forward and reverse transforms have inconsistent CD matrix: "
            << sipForward.getCDMatrix() << "\n!=\n" << sipReverse.getCDMatrix();
        throw LSST_EXCEPT(
            pex::exceptions::InvalidParameterError,
            oss.str()
        );
    }
    Eigen::MatrixXd sipA(sipForward.getPoly().getXCoeffs().asEigen());
    Eigen::MatrixXd sipB(sipForward.getPoly().getYCoeffs().asEigen());
    Eigen::MatrixXd sipAP(sipReverse.getPoly().getXCoeffs().asEigen());
    Eigen::MatrixXd sipBP(sipReverse.getPoly().getYCoeffs().asEigen());
    // TanWcs uses strings for coordinate systems, while Coord uses an enum.
    // Frustratingly, there's no way to convert from the enum to the string.
    std::string coordSys;
    switch (skyOrigin.getCoordSystem()) {
    case afw::coord::ICRS:
        coordSys = "ICRS";
        break;
    case afw::coord::FK5:
        coordSys = "FK5";
        break;
    default:
        throw LSST_EXCEPT(
            pex::exceptions::InvalidParameterError,
            "Coordinate system not supported"
        );
    }
    return std::make_shared<afw::image::TanWcs>(
        skyOrigin.getPosition(afw::geom::degrees),
        sipForward.getPixelOrigin(),
        sipForward.getCDMatrix().getMatrix(),
        sipA, sipB, sipAP, sipBP,
        skyOrigin.getEpoch(),
        coordSys
    );
}

}}} // namespace lsst::meas::astrom
