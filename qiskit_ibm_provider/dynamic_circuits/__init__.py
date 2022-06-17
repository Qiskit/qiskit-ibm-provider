# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
==============================================================
Dynamic Circuits (:mod:`qiskit_ibm_provider.dynamic_circuits`)
==============================================================

.. currentmodule:: qiskit_ibm_provider.dynamic_circuits

A collection of tools for working with IBM Quantum's next-generation
backends that support advanced "dynamic circuit" capabilities. Ie.,
circuits with support for classical control-flow/feedback based off
of measurement results.

Example Usage on a Supporting Backend
=====================================

.. jupyter-execute::
    :hide-code:
    :hide-output:

    from qiskit_ibm_provider.test.ibm_provider_mock import mock_get_backend
    mock_get_backend('FakePerth')

.. jupyter-execute::

    from qiskit_ibm_provider import IBMProvider
    import qiskit_ibm_provider.jupyter

    provider = IBMProvider(hub='ibm-q')
    backend = provider.get_backend('ibm_perth')



Scheduling & Dynamical Decoupling
=================================
.. autosummary::
   :toctree: ../stubs/


"""

foo = 1
