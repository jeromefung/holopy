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
Defines Scatterers, a scatterer that consists of other scatterers,
including scattering primitives (e.g. Sphere) or other Scatterers
scatterers (e.g. two trimers).

.. moduleauthor:: Vinothan N. Manoharan <vnm@seas.harvard.edu>
'''


from copy import copy
from numbers import Number
import warnings

import numpy as np

from holopy.scattering.scatterer.scatterer import Scatterer
from holopy.core.math import rotate_points
from holopy.core.utils import ensure_array, dict_without


class Scatterers(Scatterer):
    '''
    Contains optical and geometrical properties of a a composite
    scatterer.  A Scatterers can consist of multiple scattering
    primitives (e.g. Sphere) or other Scatterers scatterers.

    Attributes
    ----------
    scatterers : list
        List of scatterers that make up this object
    ties : dict or None (optional)
        dict indicating parameters to tie of the form: {'r': '0:r', '1:r'}

    Methods
    -------
    parameters [property]
        Dictionary of composite's unique parameters, accounting for ties.
    raw_parameters [property]
        Dictionary of all parameters in constituent scatterer objects. Does
        not account for ties.
    add(scatterer)
        Adds a new scatterer to the composite.
    from_parameters
    translated
    rotated

    Notes
    -----
    Stores information about components in a tree.  This is the most
    generic container for a collection of scatterers.
    '''

    # this uses the composite design pattern
    # see http://en.wikipedia.org/wiki/Composite_pattern
    # and
    # http://stackoverflow.com/questions/1175110/python-classes-for-simple-gtd-app
    # for a python example

    def __init__(self, scatterers=None, ties=None):
        '''
        Parameters
        ----------
        scatterers : list
            List of scatterers that make up this object
        ties : dict or None (optional)
            dict indicating parameters to tie of the form: {'r': '0:r', '1:r'}
        '''
        if ties is None:
            ties = {}
        self.ties = ties
        if scatterers is None:
            scatterers = []
        self.scatterers = scatterers
        self._find_new_ties()
        self._check_ties()

    def add(self, scatterer):
        self.scatterers.append(scatterer)
        self._find_new_ties()
        self._check_ties()

    def __getitem__(self, key):
        return self.scatterers[key]

    def get_component_list(self):
        components = []
        for s in self.scatterers:
            if isinstance(s, self.__class__):
                components += s.get_component_list()
            else:
                components.append(s)
        return components

    def add_tie(self, old_name, new_name):
        if old_name in self.ties.keys():
            self.ties[old_name].append(new_name)
        elif old_name in self._all_ties:
            tie_name = self._reversed_ties[old_name]
            self.ties[tie_name].append(new_name)
        else:
            tie_name = new_name.split(':', 1)[1]
            if tie_name in self.ties.keys():
                tie_name = new_name
            self.ties[tie_name] = [new_name, old_name]
        self._check_ties()

    def _find_new_ties(self):
        reference_parameters = self.raw_parameters
        for fullkey, par in reference_parameters.items():
            if fullkey not in self._all_ties:
                # not already in the list of ties, so check if it should be
                for ref_key, ref_par in dict_without(
                        reference_parameters, fullkey).items():
                    # can't simply check par in parameters because then two
                    # priors defined separately, but identically will match
                    # whereas this way they are counted as separate objects.
                    if par is ref_par and not isinstance(par, Number):
                        self.add_tie(ref_key, fullkey)
                        break

    def _check_ties(self):
        raw_parameters = self.raw_parameters
        for tied_name, raw_names in self.ties.items():
            for raw_name in raw_names:
                if raw_name not in raw_parameters.keys():
                    msg = ('Tied parameter {} not present in raw parameters '
                           '{}.').format(raw_name, raw_parameters.keys())
                    raise ValueError(msg)
            tied_val = raw_parameters[raw_names[0]]
            for raw_name in raw_names:
                if not raw_parameters[raw_name] == tied_val:
                    msg = ('Tied parameters {} and {} are not equal but have '
                           'values {} and {}.').format(raw_name, raw_names[0],
                           raw_parameters[raw_name], tied_val)
                    raise ValueError(msg)

    @property
    def _reversed_ties(self):
        reversed_ties = {}
        for tiename, ties in self.ties.items():
            reversed_ties.update({tie: tiename for tie in ties})
        return reversed_ties

    @property
    def _all_ties(self):
        return sum(self.ties.values(), [])

    @property
    def raw_parameters(self):
        parameters = {}
        for i, scatterer in enumerate(self.scatterers):
            single_scatterer_parameters = {'{0}:{1}'.format(i, key): val
                            for key, val in scatterer.parameters.items()}
            parameters.update(single_scatterer_parameters)
        return parameters

    @property
    def parameters(self):
        self._check_ties()
        raw_parameters = self.raw_parameters
        parameters = {key: val for key, val in raw_parameters.items()
                      if key not in self._all_ties}
        ties = {tied_name: raw_parameters[raw_names[0]] for
                tied_name, raw_names in self.ties.items()}
        parameters.update(ties)
        return parameters

    def from_parameters(self, new_parameters, overwrite=False):
        '''
        Makes a new object similar to self with values as given in parameters.
        This returns a physical object, so any priors are replaced with their
        guesses if not included in passed-in parameters.

        Parameters
        ----------
        parameters : dict
            dictionary of parameters to use in the new object.
            Keys should match those of self.parameters.
        overwrite : bool (optional)
            if True, constant values are replaced by those in parameters
        '''
        n_scatterers = len(self.scatterers)
        collected = [{} for i in range(n_scatterers)]
        for tied_name, raw_names in self.ties.items():
            try:
                tied_val = new_parameters[tied_name]
                new_parameters.update({name: tied_val for name in raw_names})
            except KeyError:
                pass
        for key, val in new_parameters.items():
            parts = key.split(':', 1)
            if len(parts) == 2:
                n = int(parts[0])
                par = parts[1]
                collected[n][par] = val
        scatterers = [scat.from_parameters(pars, overwrite)
                         for scat, pars in zip(self.scatterers, collected)]
        self_dict = dict(self._iteritems())
        self_dict['scatterers'] = scatterers
        return type(self)(**self_dict)

    def _prettystr(self, level, indent="  "):
        '''
        Generate pretty string representation of object by recursion.
        Used by __str__.
        '''
        out = level*indent + self.__class__.__name__ + '\n'
        for s in self.scatterers:
            if isinstance(s, self.__class__):
                out = out + s._prettystr(level+1)
            else:
                out = out + (level+1)*indent + s.__str__() + '\n'
        return out

    def __str__(self):
        '''
        Pretty print the nested tree of scatterers
        '''
        return self._prettystr(0)


    def translated(self, coord1, coord2=None, coord3=None):
        """
        Make a copy of this scatterer translated to a new location

        Parameters
        ----------
        x, y, z : float
            Value of the translation along each axis

        Returns
        -------
        translated : Scatterer
            A copy of this scatterer translated to a new location
        """
        if coord2 is None and len(ensure_array(coord1)==3):
            #entered translation vector
            trans_coords = ensure_array(coord1)
        elif coord2 is not None and coord3 is not None:
            #entered 3 coords
            trans_coords = np.array([coord1, coord2, coord3])
        else:
            raise InvalidScatterer(self, "Cannot interpret translation coordinates")

        trans = [s.translated(trans_coords) for s in self.scatterers]
        new = copy(self)
        new.scatterers = trans
        return new

    def rotated(self, ang1, ang2=None, ang3=None):

        if ang2 is None and len(ensure_array(ang1)==3):
            #entered rotation angle tuple
            alpha, beta, gamma = ang1
        elif ang2 is not None and ang3 is not None:
            #entered 3 angles
            alpha=ang1; beta=ang2; gamma=ang3
        else:
            raise InvalidScatterer(self, "Cannot interpret rotation coordinates")

        centers = np.array([s.center for s in self.scatterers])
        com = centers.mean(0)

        new_centers = com + rotate_points(centers - com, alpha, beta, gamma)

        scatterers = []

        for i in range(len(self.scatterers)):
            scatterers.append(self.scatterers[i].translated(
                *(new_centers[i,:] - centers[i,:])).rotated(alpha, beta, gamma))

        new = copy(self)
        new.scatterers = scatterers

        return new

    def in_domain(self, points):
        ind = self.scatterers[0].contains(points).astype('int')
        for i, s in enumerate(self.scatterers[1:]):
            contained = s.contains(points)
            nz = np.nonzero(contained)
            ind[nz] = i+1
        return ind

    def index_at(self, point):
        try:
            # This will pick out the first scatterer if you have
            # multiple overlapping ones. You shouldn't really have
            # overlapping scatterers with different indicies, so this
            # shouldn't be a problem
            return self.scatterers[self.in_domain(point)[0]].index_at(point)
        except TypeError:
            return None

    def select(self, keys):
        new = copy(self)
        new.scatterers = [s.select(keys) for s in self.scatterers]
        return new
