#!/usr/bin/env python3
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
from subprocess import call
import sys
import multiprocessing

t = ['nosetests']

if len(sys.argv) > 1 and sys.argv[1] == 'coverage':
    t.extend(['--with-coverage', '--cover-package=holopy', '--cover-erase'])
else:
    t.extend(['--processes={0}'.format(multiprocessing.cpu_count())] +
             sys.argv[2:])
t.extend(['--process-timeout=120'])

print((' '.join(t)))
returncode = call(t)
if returncode is not 0:
    sys.exit(returncode)

doctest = ['sphinx-build', '-b', 'doctest', './docs/source', './docs/build']
print((' '.join(doctest)))
returncode = call(doctest)
if returncode is not 0:
    sys.exit(returncode)
