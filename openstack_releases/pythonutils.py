# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import logging
import os
import os.path
import xmlrpc.client

from packaging import utils as packaging_utils
import requests

from openstack_releases import processutils

LOG = logging.getLogger(__name__)


def get_sdist_name(workdir, repo):
    "Check out the code."
    dest = os.path.join(workdir, repo)
    setup_path = os.path.join(dest, 'setup.py')
    if not os.path.exists(setup_path):
        LOG.debug('did not find %s, maybe %s is not a python project',
                  setup_path, repo)
        return None
    use_tox = repo.endswith('/pbr')
    if use_tox and not os.path.exists(os.path.join(dest, '.tox', 'venv')):
        # Use tox to set up a virtualenv so we can install the
        # dependencies for the package. This only seems to be
        # necessary for pbr, but...
        processutils.check_output(
            ['tox', '-e', 'venv', '--notest'],
            cwd=dest,
        )
    if use_tox:
        python = '.tox/venv/bin/python'
    else:
        python = 'python'
    # Run it once and discard the result to ensure any setup_requires
    # dependencies are installed.
    cmd = [python, 'setup.py', '--name']
    processutils.check_output(cmd, cwd=dest)
    # Run it again to get a clean version of the name.
    LOG.debug('Running: %s in %s' % (' '.join(cmd), dest))
    out = processutils.check_output(cmd, cwd=dest).decode('utf-8')
    LOG.debug('Results: %s' % (out,))
    name = out.splitlines()[-1].strip()
    return name


def get_pypi_info(dist_name):
    "Return PyPI information for the distribution."
    canonical_name = packaging_utils.canonicalize_name(dist_name)
    LOG.debug('looking at PyPI for {!r}'.format(canonical_name))
    url = 'https://pypi.org/project/{}/json'.format(canonical_name)
    LOG.debug(url)
    try:
        return requests.get(url).json()
    except json.decoder.JSONDecodeError:
        return {}


def _get_pypi_roles(dist_name):
    client = xmlrpc.client.ServerProxy('https://pypi.org/project')
    LOG.debug('retrieving roles for {!r}'.format(
        dist_name))
    return client.package_roles(dist_name)


def get_pypi_uploaders(dist_name):
    roles = _get_pypi_roles(dist_name)
    if not roles:
        canonical_name = packaging_utils.canonicalize_name(dist_name)
        roles = _get_pypi_roles(canonical_name)
    uploaders = set(
        acct
        for role, acct in roles
        if role in ('Owner', 'Maintainer')
    )
    LOG.debug('found: {}'.format(sorted(uploaders)))
    return uploaders
