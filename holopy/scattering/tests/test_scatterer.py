# Copyright 2011-2016, Vinothan N. Manoharan, Thomas G. Dimiduk,
# Rebecca W. Perry, Jerome Fung, Ryan McGorty, Anna Wang, Solomon Barkley
#
# This file is part of HoloPy.
#
# HoloPy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HoloPy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HoloPy.  If not, see <http://www.gnu.org/licenses/>.
'''
Test construction and manipulation of Scatterer objects.

.. moduleauthor:: Vinothan N. Manoharan <vnm@seas.harvard.edu>
'''

import unittest

import numpy as np
import xarray as xr
from numpy.testing import assert_equal, assert_raises, assert_allclose
from nose.plugins.attrib import attr

from holopy.core import detector_grid
from holopy.scattering import (
    Sphere, Spheres, Scatterer, Ellipsoid, Scatterers, calc_holo)
from holopy.scattering.scatterer.ellipsoid import isnumber
from holopy.scattering.scatterer.scatterer import (
    find_bounds, _expand_parameters, _interpret_parameters)
from holopy.inference.prior import ComplexPrior, Uniform
from holopy.scattering.errors import InvalidScatterer, MissingParameter


@attr('fast')
def test_Sphere_construction():
    s = Sphere(n=1.59, r=5e-7, center=(1e-6, -1e-6, 10e-6))
    s = Sphere(n=1.59, r=5e-7)
    # index can be complex
    s = Sphere(n=1.59+0.0001j, r=5e-7)
    s = Sphere()

    with assert_raises(InvalidScatterer):
        Sphere(n=1.59, r=-2, center=(1, 1, 1))

    # now test multilayer spheres
    cs = Sphere(n=(1.59, 1.59), r=(5e-7, 1e-6), center=(1e-6, -1e-6, 10e-6))
    cs = Sphere(n=(1.59, 1.33), r=(5e-7, 1e-6))
    # index can be complex
    cs = Sphere(n=(1.59+0.0001j, 1.33+0.0001j), r=(5e-7, 1e-6))
    center = np.array([1e-6, -1e-6, 10e-6])
    cs = Sphere(n=(1.59+0.0001j, 1.33+0.0001j), r=(5e-7, 1e-6), center=center)


@attr("fast")
def test_Ellipsoid():
    s = Ellipsoid(n=1.57, r=(1, 2, 3), center=(3, 2, 1))
    assert_equal(s.n, 1.57)
    assert_equal(s.r, (1, 2, 3))
    assert_equal(s.center, (3, 2, 1))
    assert_equal(str(s)[0:9], 'Ellipsoid')
    assert_equal(True, isnumber(3))
    assert_equal(False, isnumber('p'))


@attr('fast')
def test_Sphere_construct_list():
    # specify center as list
    center = [1e-6, -1e-6, 10e-6]
    s = Sphere(n=1.59+0.0001j, r=5e-7, center=center)
    assert_equal(s.center, np.array(center))


@attr('fast')
def test_Sphere_construct_tuple():
    # specify center as list
    center = (1e-6, -1e-6, 10e-6)
    s = Sphere(n=1.59+0.0001j, r=5e-7, center=center)
    assert_equal(s.center, np.array(center))


@attr('fast')
def test_Sphere_construct_array():
    # specify center as list
    center = np.array([1e-6, -1e-6, 10e-6])
    s = Sphere(n=1.59+0.0001j, r=5e-7, center=center)
    assert_equal(s.center, center)

    with assert_raises(InvalidScatterer) as cm:
        Sphere(center=1)
    assert_equal(str(cm.exception), "Invalid scatterer of type "
                 "Sphere.\ncenter specified as 1, center should be specified "
                 "as (x, y, z)")


@attr('fast')
def test_Sphere_parameters():
    s = Sphere(n=1.59+1e-4j, r=5e-7, center=(1e-6, -1e-6, 10e-6))
    assert_equal(
        s.parameters,
        dict([
            ('center.0', 1e-6),
            ('center.1', -1e-6),
            ('center.2', 1e-5),
            ('n', 1.59+1e-4j),
            ('r', 5e-07)]))

    sp = s.from_parameters(s.parameters)
    assert_equal(s.r, sp.r)
    assert_equal(s.n, sp.n)
    assert_equal(s.center, sp.center)


class TestParameterHandling(unittest.TestCase):
    expanded = {'a': 0, 'b.0':0.5, 'b.1':1, 'b.2':2, 'c:c1':3, 'c:c2':4,
                'd.real':5, 'd.imag':6, 'e:e1.real':7, 'e:e1.imag':8,
                'e:e2.0':9, 'e:e2.1':10, 'f:Left:H':11, 'f:Left:He':12,
                'f:Left:Li':13, 'f:Right:H':14, 'f:Right:He':15,
                'f:Right:Li':16}

    @attr("fast")
    def test_expand_parameters(self):
        array_f = xr.DataArray([[11,12,13], [14,15,16]], dims=['d2','d3'],
            coords={'d3':['H','He','Li'],'d2':['Left','Right']})
        compressed = {'a':0, 'b':[0.5, 1, 2], 'c':{'c1':3, 'c2':4},
                      'd':ComplexPrior(5, 6),
                      'e':{'e1':ComplexPrior(7, 8), 'e2':[9,10]},'f':array_f}
        expansion = dict(_expand_parameters(compressed.items()))
        self.assertTrue(expansion == self.expanded)

    @attr("fast")
    def test_interpret_parameters(self):
        dict_f = {'Left': {'H': 11, 'He': 12, 'Li': 13},
                  'Right': {'H': 14, 'He': 15, 'Li': 16}}
        simple_compressed = {'a':0, 'b':[0.5, 1, 2], 'c':{'c1':3, 'c2':4},
                             'd':5+6j, 'e':{'e1':7+8j, 'e2':[9,10]},'f':dict_f}
        compression = _interpret_parameters(self.expanded)
        self.assertTrue(compression == simple_compressed)


def test_from_parameters():
    s_prior = Sphere(n=1.6, r=Uniform(0.5, 0.7), center=[10, 10, 10])
    s_guess = Sphere(n=1.6, r=0.6, center=[10,10,10])
    s_new_r = Sphere(n=1.6, r=0.7, center=[10,10,10])
    s_new_nr= Sphere(n=1.7, r=0.7, center=[10,10,10])
    pars = {'n':1.7, 'r':0.7}
    assert_equal(s_prior.from_parameters({}), s_guess)
    assert_equal(s_prior.from_parameters(pars, overwrite=False), s_new_r)
    assert_equal(s_prior.from_parameters(pars, overwrite=True), s_new_nr)


@attr('fast')
def test_Composite_construction():
    # empty composite
    comp_empty = Scatterers()

    # composite of multiple spheres
    s1 = Sphere(n = 1.59, r = 5e-7, center = (1e-6, -1e-6, 10e-6))
    s2 = Sphere(n = 1.59, r = 1e-6, center=[0,0,0])
    s3 = Sphere(n = 1.59+0.0001j, r = 5e-7, center=[5e-6,0,0])
    comp_spheres = Scatterers(scatterers=[s1, s2, s3])

    # heterogeneous composite
    cs = Sphere(n=(1.59+0.0001j, 1.33+0.0001j), r=(5e-7, 1e-6),
                      center=[-5e-6, 0,0])
    comp = Scatterers(scatterers=[s1, s2, s3, cs])

    assert_equal(comp.in_domain([-5e-6,0,0]), 3)
    assert_equal(comp.index_at([-5e-6,0,0]), cs.n[0])

    # multi-level composite (contains another composite)
    s4 = Sphere(center=[0, 5e-6, 0])
    comp_spheres.add(s4)
    comp2 = Scatterers(scatterers=[comp_spheres, comp])

    # even more levels
    comp3 = Scatterers(scatterers=[comp2, cs])


def test_Composite_tying():
    # tied parameters
    n1 = Uniform(1.59,1.6, guess=1.59)
    sc = Spheres(
        [Sphere(n=n1, r=Uniform(0.5, 0.7), center=np.array([10., 10., 20.])),
         Sphere(n=n1, r=Uniform(0.5, 0.7), center=np.array([ 9., 11., 21.]))])
    assert_equal(len(sc.parameters), 9)
    assert_equal(sc.parameters['n'].guess, 1.59)
    assert_equal(sc.parameters['0:r'], sc.parameters['1:r'])


@attr('fast')
def test_like_me():
    s = Sphere(n = 1.59, r = .5, center = (1, -1, 10))
    s2 = s.like_me(center = (0, 2, 10))

    assert_equal(s.r, s2.r)
    assert_equal(s.n, s2.n)
    assert_equal(s2.center, (0, 2, 10))


@attr('fast')
def test_translate():
    s = Sphere(n = 1.59, r = .5, center = (0, 0, 0))
    s2 = s.translated(1, 1, 1)
    assert_equal(s.r, s2.r)
    assert_equal(s.n, s2.n)
    assert_allclose(s2.center, (1, 1, 1))


@attr("fast")
def test_find_bounds():
    s = Sphere(n = 1.59, r = .5e-6, center = (0, 0, 0))
    assert_allclose(find_bounds(s.indicators.functions[0])[0], np.array([-s.r,s.r]), rtol=0.1)
    s = Sphere(n = 1.59, r = .5, center = (0, 0, 0))
    assert_allclose(find_bounds(s.indicators.functions[0])[0], np.array([-s.r,s.r]), rtol=0.1)
    s = Sphere(n = 1.59, r = .5e6, center = (0, 0, 0))
    assert_allclose(find_bounds(s.indicators.functions[0])[0], np.array([-s.r,s.r]), rtol=0.1)


@attr("fast")
def test_sphere_nocenter():
    sphere = Sphere(n = 1.59, r = .5)
    schema = detector_grid(spacing=.1, shape=1)
    assert_raises(MissingParameter, calc_holo, schema, sphere, 1.33, .66, [1, 0])


@attr("fast")
def test_ellipsoid():
    test = Ellipsoid(n = 1.585, r = [.4,0.4,1.5], center = [10,10,20])
    assert_equal(test.voxelate(.4), np.array(
        [[[0., 0., 0., 0., 0., 0., 0., 0.],
          [0., 0., 0., 0., 0., 0., 0., 0.],
          [0., 0., 0., 0., 0., 0., 0., 0.]],
         [[0., 0., 0., 0., 0., 0., 0., 0.],
          [0., 1.585, 1.585, 1.585, 1.585, 1.585, 1.585, 1.585],
          [0., 0., 0., 0., 0., 0., 0., 0.]],
         [[0., 0., 0., 0., 0., 0., 0., 0.],
          [0., 0., 0., 0., 0., 0., 0., 0.],
          [0., 0., 0., 0., 0., 0., 0., 0.]]]))


if __name__ == '__main__':
    unittest.main()

